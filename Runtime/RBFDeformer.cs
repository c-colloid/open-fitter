// ----------------------------------------------------------------------------
// Copyright (C) [2025] tallcat
//
// This file is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This file is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
// See the accompanying LICENSE file for more details.
// ----------------------------------------------------------------------------

using System.Collections.Generic;
using UnityEngine;
using Unity.Collections;
using Unity.Jobs;
using Unity.Mathematics;
using Unity.Burst;
using System.IO;
using Newtonsoft.Json;

[System.Serializable]
public class RBFShapeKeyData
{
    public string name;
    public float weight; // 50.0 or 100.0
    public float epsilon;
    public List<List<float>> centers;
    public List<List<float>> weights;
    public List<List<float>> poly_weights;
    public List<float> bounds_min; // [x, y, z]
    public List<float> bounds_max; // [x, y, z]
}

[System.Serializable]
public class RBFData
{
    public float epsilon;
    public List<List<float>> centers;
    public List<List<float>> weights;
    public List<List<float>> poly_weights;
    public List<RBFShapeKeyData> shape_keys; // New field for additional shape keys
}

[ExecuteInEditMode] // エディタ上で動作することを明示
public class RBFDeformer : MonoBehaviour
{
    [Tooltip("Drag & Drop the RBF JSON file here.")]
    public TextAsset rbfDataJson;
    
    // Legacy support or internal path use
    [HideInInspector] public string jsonFilePath = "rbf_data.json";

    // ターゲット情報の定義
    [System.Serializable]
    public class TargetMeshInfo
    {
        public SkinnedMeshRenderer smr;
        public Mesh originalMesh;
        public Mesh deformedMesh;
    }

    [SerializeField] private List<TargetMeshInfo> targets = new List<TargetMeshInfo>();
    public List<TargetMeshInfo> Targets => targets;

    // Job用データ (共通)
    private NativeArray<float3> centers;
    private NativeArray<float3> weights;
    private NativeArray<float3> polyWeights;
    
    private float epsilon;

    // Additional Shape Keys Data
    private List<RBFShapeKeyRuntimeData> shapeKeyRuntimeDataList = new List<RBFShapeKeyRuntimeData>();

    private class RBFShapeKeyRuntimeData
    {
        public string name;
        public float weight;
        public float epsilon;
        public NativeArray<float3> centers;
        public NativeArray<float3> weights;
        public NativeArray<float3> polyWeights;
        public float3 boundsMin;
        public float3 boundsMax;
        public bool useBounds;
    }

    // コンポーネント削除時やスクリプト再コンパイル時にメモリを解放
    void OnDisable()
    {
        DisposeNativeArrays();
    }

    void OnDestroy()
    {
        DisposeNativeArrays();
    }

    public void DisposeNativeArrays()
    {
        if (centers.IsCreated) centers.Dispose();
        if (weights.IsCreated) weights.Dispose();
        if (polyWeights.IsCreated) polyWeights.Dispose();

        foreach (var data in shapeKeyRuntimeDataList)
        {
            if (data.centers.IsCreated) data.centers.Dispose();
            if (data.weights.IsCreated) data.weights.Dispose();
            if (data.polyWeights.IsCreated) data.polyWeights.Dispose();
        }
        shapeKeyRuntimeDataList.Clear();
    }

    // エディタから「実行」ボタンで呼ばれる一括処理関数
    public void RunDeformationInEditor()
    {
        // 1. メッシュの準備 (子階層を含む全て)
        InitMeshes();

        // 2. データのロード
        if (!LoadRBFData()) return;

        // 3. 計算と適用
        ApplyRBFToAll();
    }

    void InitMeshes()
    {
        var smrs = GetComponentsInChildren<SkinnedMeshRenderer>(true);

        // 既存のターゲット情報を保持するためのマップ
        var existing = new Dictionary<Component, TargetMeshInfo>();
        foreach (var t in targets)
        {
            if (t.smr != null) existing[t.smr] = t;
        }

        targets.Clear();

        // SkinnedMeshRendererの処理
        foreach (var smr in smrs)
        {
            if (existing.TryGetValue(smr, out var info))
            {
                // 既存情報の引継ぎ
                if (info.deformedMesh == null)
                {
                    info.deformedMesh = CreatePreviewMesh(info.originalMesh);
                    smr.sharedMesh = info.deformedMesh;
                }
                targets.Add(info);
            }
            else
            {
                // 新規登録
                Mesh current = smr.sharedMesh;
                if (current == null) continue;

                // 既にプレビューメッシュになっている場合はスキップ（二重適用防止）
                if (current.name.EndsWith("_Preview"))
                {
                    Debug.LogWarning($"Skipping {smr.name} because it seems to be already deformed (Mesh: {current.name})");
                    continue;
                }

                info = new TargetMeshInfo { smr = smr, originalMesh = current };
                info.deformedMesh = CreatePreviewMesh(current);
                smr.sharedMesh = info.deformedMesh;
                targets.Add(info);
            }
        }
    }

    Mesh CreatePreviewMesh(Mesh original)
    {
        var m = Instantiate(original);
        m.name = original.name + "_Preview";
        m.hideFlags = HideFlags.DontSaveInEditor | HideFlags.DontSaveInBuild;
        return m;
    }

    bool LoadRBFData()
    {
        string jsonStr = "";

        if (rbfDataJson != null)
        {
            jsonStr = rbfDataJson.text;
        }
        else
        {
            // Fallback to file path logic if TextAsset is not set
            string path = Path.Combine(Application.dataPath, jsonFilePath);
            if (!File.Exists(path))
            {
                Debug.LogError("RBF Data not found. Please assign a JSON file to the 'Rbf Data Json' field.");
                return false;
            }
            jsonStr = File.ReadAllText(path);
        }

        try 
        {
            var data = JsonConvert.DeserializeObject<RBFData>(jsonStr);

            this.epsilon = data.epsilon;
            
            DisposeNativeArrays(); // 安全のためリセット

            // 軸変換: Blender (Right-Handed Z-Up) -> Unity (Left-Handed Y-Up)
            // Mapping: (-x, z, -y)
            // これはBoneDeformer.csの実装と一致させるための変更です。
            var centersArr = ConvertToUnitySpace(data.centers);
            var weightsArr = ConvertToUnitySpace(data.weights);
            var polyArr = ConvertToUnitySpace(data.poly_weights);

            // 多項式項の入力座標系の補正
            // Poly = Bias + C_x * x_in + C_y * y_in + C_z * z_in
            // Unity入力 (x_u, y_u, z_u) に対して:
            // x_in_blender = -x_u
            // y_in_blender = -z_u
            // z_in_blender = y_u
            
            // Row 0 (Bias): 変換済み (ConvertToUnitySpaceで出力座標系は変換されている)
            // Row 1 (X coeff): x_in = -x_u なので、係数を反転
            polyArr[1] = -polyArr[1];
            
            // Row 2 (Y coeff) & Row 3 (Z coeff):
            // Term Y: C_y * y_in = C_y * (-z_u) -> UnityのZ係数(Row 3)に -C_y をセット
            // Term Z: C_z * z_in = C_z * (y_u)  -> UnityのY係数(Row 2)に C_z をセット
            
            float3 oldRow2 = polyArr[2]; // C_y (converted to Unity output space)
            float3 oldRow3 = polyArr[3]; // C_z (converted to Unity output space)
            
            polyArr[2] = oldRow3;  // New Y coeff = Old Z coeff
            polyArr[3] = -oldRow2; // New Z coeff = -Old Y coeff

            centers = new NativeArray<float3>(centersArr, Allocator.Persistent);
            weights = new NativeArray<float3>(weightsArr, Allocator.Persistent);
            polyWeights = new NativeArray<float3>(polyArr, Allocator.Persistent);

            // Load Additional Shape Keys
            if (data.shape_keys != null)
            {
                foreach (var skData in data.shape_keys)
                {
                    var skCentersArr = ConvertToUnitySpace(skData.centers);
                    var skWeightsArr = ConvertToUnitySpace(skData.weights);
                    var skPolyArr = ConvertToUnitySpace(skData.poly_weights);

                    // Apply same polynomial correction
                    skPolyArr[1] = -skPolyArr[1];
                    float3 skOldRow2 = skPolyArr[2];
                    float3 skOldRow3 = skPolyArr[3];
                    skPolyArr[2] = skOldRow3;
                    skPolyArr[3] = -skOldRow2;

                    // Parse Bounds if available
                    float3 bMin = new float3(float.MinValue, float.MinValue, float.MinValue);
                    float3 bMax = new float3(float.MaxValue, float.MaxValue, float.MaxValue);
                    bool useBounds = false;

                    if (skData.bounds_min != null && skData.bounds_max != null && skData.bounds_min.Count == 3)
                    {
                        // Convert Bounds to Unity Space
                        // Blender (x, y, z) -> Unity (-x, z, -y)
                        // Since we are flipping axes, Min/Max relationships might swap.
                        // We need to transform the corners of the AABB and re-compute the AABB in Unity space.
                        
                        Vector3[] corners = new Vector3[8];
                        float bx1 = skData.bounds_min[0]; float by1 = skData.bounds_min[1]; float bz1 = skData.bounds_min[2];
                        float bx2 = skData.bounds_max[0]; float by2 = skData.bounds_max[1]; float bz2 = skData.bounds_max[2];
                        
                        corners[0] = new Vector3(-bx1, bz1, -by1);
                        corners[1] = new Vector3(-bx2, bz1, -by1);
                        corners[2] = new Vector3(-bx1, bz2, -by1);
                        corners[3] = new Vector3(-bx2, bz2, -by1);
                        corners[4] = new Vector3(-bx1, bz1, -by2);
                        corners[5] = new Vector3(-bx2, bz1, -by2);
                        corners[6] = new Vector3(-bx1, bz2, -by2);
                        corners[7] = new Vector3(-bx2, bz2, -by2);
                        
                        Vector3 minV = corners[0];
                        Vector3 maxV = corners[0];
                        
                        foreach(var v in corners)
                        {
                            minV = Vector3.Min(minV, v);
                            maxV = Vector3.Max(maxV, v);
                        }
                        
                        bMin = minV;
                        bMax = maxV;
                        useBounds = true;
                    }

                    var runtimeData = new RBFShapeKeyRuntimeData
                    {
                        name = skData.name,
                        weight = skData.weight > 0 ? skData.weight : 100f, // Default to 100 if missing
                        epsilon = skData.epsilon,
                        centers = new NativeArray<float3>(skCentersArr, Allocator.Persistent),
                        weights = new NativeArray<float3>(skWeightsArr, Allocator.Persistent),
                        polyWeights = new NativeArray<float3>(skPolyArr, Allocator.Persistent),
                        boundsMin = bMin,
                        boundsMax = bMax,
                        useBounds = useBounds
                    };
                    shapeKeyRuntimeDataList.Add(runtimeData);
                }
            }

            return true;
        }
        catch (System.Exception e)
        {
            Debug.LogError($"JSON Load Error: {e.Message}");
            return false;
        }
    }

    float3[] ConvertToUnitySpace(List<List<float>> list)
    {
        float3[] result = new float3[list.Count];
        for (int i = 0; i < list.Count; i++)
        {
            // Blender (x, y, z) -> Unity (-x, z, -y)
            result[i] = new float3(-list[i][0], list[i][2], -list[i][1]);
        }
        return result;
    }

    void ApplyRBFToAll()
    {
        foreach (var target in targets)
        {
            if (target.originalMesh == null || target.deformedMesh == null) continue;
            
            Transform t = target.smr.transform;
            ApplyRBF(target.originalMesh, target.deformedMesh, t);
        }
        Debug.Log($"<color=cyan>[RBF Deformer]</color> Applied to {targets.Count} meshes.");
    }

    void ApplyRBF(Mesh original, Mesh deformed, Transform targetTransform)
    {
        Vector3[] meshVerts = original.vertices;
        int vertexCount = meshVerts.Length;

        // ---------------------------------------------------------
        // 1. Base Mesh Deformation
        // ---------------------------------------------------------
        
        // Job用のNativeArray確保 (一時的)
        var originalVertices = new NativeArray<float3>(vertexCount, Allocator.TempJob);
        var deformedVertices = new NativeArray<float3>(vertexCount, Allocator.TempJob);

        // データのコピー
        for(int i=0; i<vertexCount; i++) originalVertices[i] = meshVerts[i];

        var job = new RBFDeformJob
        {
            vertices = originalVertices,
            deformedVertices = deformedVertices,
            centers = centers,
            weights = weights,
            polyWeights = polyWeights,
            epsilon = epsilon,
            localToWorld = targetTransform.localToWorldMatrix,
            inverseRotation = Quaternion.Inverse(targetTransform.rotation),
            useBounds = false // Main deformation doesn't use bounds
        };

        // 実行と待機
        job.Schedule(vertexCount, 64).Complete();

        // 結果の書き戻し & ベース変形後の頂点を保持 (シェイプキー計算用)
        Vector3[] deformedBaseVerts = new Vector3[vertexCount];
        for(int i=0; i<vertexCount; i++) deformedBaseVerts[i] = deformedVertices[i];

        deformed.vertices = deformedBaseVerts;
        deformed.RecalculateNormals();
        deformed.RecalculateBounds();
        
        originalVertices.Dispose();
        deformedVertices.Dispose();

        // ---------------------------------------------------------
        // 2. BlendShape Deformation
        // ---------------------------------------------------------
        // すべてのシェイプキーに対してRBF変形を適用する
        
        deformed.ClearBlendShapes();
        int shapeCount = original.blendShapeCount;

        if (shapeCount > 0)
        {
            Vector3[] deltaVerts = new Vector3[vertexCount];
            Vector3[] deltaNormals = new Vector3[vertexCount];
            Vector3[] deltaTangents = new Vector3[vertexCount];

            for (int i = 0; i < shapeCount; i++)
            {
                string shapeName = original.GetBlendShapeName(i);
                int frameCount = original.GetBlendShapeFrameCount(i);

                for (int f = 0; f < frameCount; f++)
                {
                    float frameWeight = original.GetBlendShapeFrameWeight(i, f);
                    original.GetBlendShapeFrameVertices(i, f, deltaVerts, deltaNormals, deltaTangents);

                    // シェイプキー適用後の絶対座標を作成
                    var shapeVerticesNA = new NativeArray<float3>(vertexCount, Allocator.TempJob);
                    var deformedShapeVerticesNA = new NativeArray<float3>(vertexCount, Allocator.TempJob);

                    for (int v = 0; v < vertexCount; v++)
                    {
                        shapeVerticesNA[v] = meshVerts[v] + deltaVerts[v];
                    }

                    // RBF変形を実行
                    var shapeJob = new RBFDeformJob
                    {
                        vertices = shapeVerticesNA,
                        deformedVertices = deformedShapeVerticesNA,
                        centers = centers,
                        weights = weights,
                        polyWeights = polyWeights,
                        epsilon = epsilon,
                        localToWorld = targetTransform.localToWorldMatrix,
                        inverseRotation = Quaternion.Inverse(targetTransform.rotation),
                        useBounds = false // Main deformation doesn't use bounds
                    };
                    shapeJob.Schedule(vertexCount, 64).Complete();

                    // 新しいデルタを計算 (変形後シェイプ - 変形後ベース)
                    Vector3[] newDeltaVerts = new Vector3[vertexCount];
                    for (int v = 0; v < vertexCount; v++)
                    {
                        newDeltaVerts[v] = (Vector3)deformedShapeVerticesNA[v] - deformedBaseVerts[v];
                    }

                    // 変形されたシェイプキーを追加
                    // Note: 法線と接線のデルタはRBF変形が困難なため、元の値を維持します。
                    // 大きな変形の場合、法線が正しくない可能性がありますが、形状は維持されます。
                    deformed.AddBlendShapeFrame(shapeName, frameWeight, newDeltaVerts, deltaNormals, deltaTangents);

                    shapeVerticesNA.Dispose();
                    deformedShapeVerticesNA.Dispose();
                }
            }
            Debug.Log($"<color=cyan>[RBF Deformer]</color> Processed {shapeCount} BlendShapes for {original.name}");
        }

        // ---------------------------------------------------------
        // 3. Additional Shape Keys from RBF Data (Target Transfer)
        // ---------------------------------------------------------
        if (shapeKeyRuntimeDataList.Count > 0)
        {
            Debug.Log($"<color=cyan>[RBF Deformer]</color> Generating {shapeKeyRuntimeDataList.Count} new Shape Keys from RBF Data...");
            
            // The RBF fields for shape keys map from (Target Base) -> (Target Shape).
            // We apply this deformation to the already fitted clothing vertices (deformedBaseVerts).
            
            var fittedVerticesNA = new NativeArray<float3>(vertexCount, Allocator.TempJob);
            for(int i=0; i<vertexCount; i++) fittedVerticesNA[i] = deformedBaseVerts[i];

            // Group by name to handle multi-step keys
            // We need to group data by key name and sort by weight.
            var groupedKeys = new Dictionary<string, List<RBFShapeKeyRuntimeData>>();
            foreach(var data in shapeKeyRuntimeDataList)
            {
                if (!groupedKeys.ContainsKey(data.name)) groupedKeys[data.name] = new List<RBFShapeKeyRuntimeData>();
                groupedKeys[data.name].Add(data);
            }

            foreach (var kvp in groupedKeys)
            {
                string keyName = kvp.Key;
                var steps = kvp.Value;
                steps.Sort((a, b) => a.weight.CompareTo(b.weight)); // Sort 50, then 100
                
                // We need to track the "Current Deformed State" for this key chain.
                // Start with Base Fitted Verts.
                var currentVertsNA = new NativeArray<float3>(vertexCount, Allocator.TempJob);
                for(int i=0; i<vertexCount; i++) currentVertsNA[i] = deformedBaseVerts[i];

                foreach(var step in steps)
                {
                    var nextVertsNA = new NativeArray<float3>(vertexCount, Allocator.TempJob);

                    var skJob = new RBFDeformJob
                    {
                        vertices = currentVertsNA, // Input is previous step
                        deformedVertices = nextVertsNA,
                        centers = step.centers,
                        weights = step.weights,
                        polyWeights = step.polyWeights,
                        epsilon = step.epsilon,
                        localToWorld = targetTransform.localToWorldMatrix,
                        inverseRotation = Quaternion.Inverse(targetTransform.rotation),
                        useBounds = step.useBounds,
                        boundsMin = step.boundsMin,
                        boundsMax = step.boundsMax
                    };
                    skJob.Schedule(vertexCount, 64).Complete();
                    
                    // Calculate Delta for this frame: (Current Step Pos) - (Base Pos)
                    // Note: BlendShape delta is always relative to the Original Mesh (Base).
                    Vector3[] frameDeltas = new Vector3[vertexCount];
                    for (int v = 0; v < vertexCount; v++)
                    {
                        frameDeltas[v] = (Vector3)nextVertsNA[v] - deformedBaseVerts[v];
                    }
                    
                    // Add Frame
                    // Normals/Tangents delta are zero for now
                    Vector3[] zeroDeltas = new Vector3[vertexCount]; 
                    deformed.AddBlendShapeFrame(keyName, step.weight, frameDeltas, zeroDeltas, zeroDeltas);
                    
                    // Update current verts for next step
                    currentVertsNA.Dispose();
                    currentVertsNA = nextVertsNA;
                }
                currentVertsNA.Dispose();
            }
            fittedVerticesNA.Dispose();
        }
    }

    [BurstCompile]
    struct RBFDeformJob : IJobParallelFor
    {
        [ReadOnly] public NativeArray<float3> vertices;
        [ReadOnly] public NativeArray<float3> centers;
        [ReadOnly] public NativeArray<float3> weights;
        [ReadOnly] public NativeArray<float3> polyWeights;
        [ReadOnly] public float epsilon;
        [ReadOnly] public float4x4 localToWorld;
        [ReadOnly] public quaternion inverseRotation;
        
        // Masking
        [ReadOnly] public bool useBounds;
        [ReadOnly] public float3 boundsMin;
        [ReadOnly] public float3 boundsMax;

        [WriteOnly] public NativeArray<float3> deformedVertices;

        public void Execute(int i)
        {
            float3 p_local = vertices[i];
            float3 p_world = math.transform(localToWorld, p_local);
            
            // Bounds Check (Masking)
            if (useBounds)
            {
                if (p_world.x < boundsMin.x || p_world.x > boundsMax.x ||
                    p_world.y < boundsMin.y || p_world.y > boundsMax.y ||
                    p_world.z < boundsMin.z || p_world.z > boundsMax.z)
                {
                    // Outside of active region -> No deformation
                    deformedVertices[i] = p_local;
                    return;
                }
            }
            
            float3 displacement = float3.zero;
            float eps2 = epsilon * epsilon;

            for (int j = 0; j < centers.Length; j++)
            {
                float distSq = math.distancesq(p_world, centers[j]);
                float phi = math.sqrt(distSq + eps2);
                displacement += weights[j] * phi;
            }

            displacement += polyWeights[0];
            displacement += polyWeights[1] * p_world.x;
            displacement += polyWeights[2] * p_world.y;
            displacement += polyWeights[3] * p_world.z;

            float3 disp_local = math.rotate(inverseRotation, displacement);
            deformedVertices[i] = p_local + disp_local;
        }
    }
}