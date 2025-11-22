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

// RBFDeformerEditor.cs

using UnityEngine;
using UnityEditor;
using System.IO;

[CustomEditor(typeof(RBFDeformer))]
public class RBFDeformerEditor : Editor
{
    private SerializedProperty jsonPathProp;
    private SerializedProperty originalMeshProp;
    private SerializedProperty deformedMeshProp;

    private void OnEnable()
    {
        jsonPathProp = serializedObject.FindProperty("jsonFilePath");
        originalMeshProp = serializedObject.FindProperty("originalMesh");
        deformedMeshProp = serializedObject.FindProperty("deformedMesh");
    }

    public override void OnInspectorGUI()
    {
        RBFDeformer deformer = (RBFDeformer)target;
        serializedObject.Update();

        // ----------------------------------------------------
        // 1. RBF Data Path Setup
        // ----------------------------------------------------
        GUILayout.Label("RBF Data Configuration", EditorStyles.boldLabel);
        
        EditorGUILayout.PropertyField(jsonPathProp, new GUIContent("JSON Path (Assets Relative)"));

        // ファイルブラウザボタンを追加
        if (GUILayout.Button("Browse for RBF JSON File (.json)"))
        {
            string selectedPath = EditorUtility.OpenFilePanel(
                "Select RBF Data JSON", 
                Application.dataPath, // 初期ディレクトリをAssetsに設定
                "json"
            );

            if (!string.IsNullOrEmpty(selectedPath))
            {
                // 絶対パスが Assets フォルダ以下にあることを確認
                if (selectedPath.StartsWith(Application.dataPath))
                {
                    // Assets/ を基準とした相対パスに変換
                    // +1 は Path.DirectorySeparatorChar ('/') をスキップするため
                    string relativePath = selectedPath.Substring(Application.dataPath.Length + 1);
                    jsonPathProp.stringValue = relativePath;
                }
                else
                {
                    Debug.LogError("Error: The selected JSON file must be located within the project's 'Assets' folder structure for consistent loading.");
                }
            }
        }
        
        // 状態表示 (エディタ拡張からアクセスするためのReadOnlyフィールド)
        GUILayout.Space(5);
        EditorGUILayout.LabelField("Current Status:", EditorStyles.miniBoldLabel);
        GUI.enabled = false; // 読み取り専用にする
        EditorGUILayout.PropertyField(originalMeshProp, new GUIContent("Original Mesh"));
        EditorGUILayout.PropertyField(deformedMeshProp, new GUIContent("Deformed Mesh"));
        GUI.enabled = true;
        
        serializedObject.ApplyModifiedProperties();
        
        // ----------------------------------------------------
        // 2. Deformation Workflow
        // ----------------------------------------------------

        GUILayout.Space(15);
        GUILayout.Label("Workflow (Edit Mode Only)", EditorStyles.boldLabel);

        if (GUILayout.Button("Run RBF & Preview", GUILayout.Height(30)))
        {
            deformer.RunDeformationInEditor();
            SceneView.RepaintAll();
        }

        GUILayout.Space(10);
        
        // ----------------------------------------------------
        // 3. Export Options
        // ----------------------------------------------------
        
        bool hasMesh = deformer.DeformedMesh != null;
        
        using (new EditorGUI.DisabledScope(!hasMesh))
        {
            GUILayout.Label("Export Options", EditorStyles.boldLabel);

            if (GUILayout.Button("Save Deformed Mesh (.asset)"))
            {
                SaveAsMeshAsset(deformer);
            }

            if (GUILayout.Button("Create Mesh with BlendShape"))
            {
                AddBlendShapeToOriginal(deformer);
            }
        }
    }

    void SaveAsMeshAsset(RBFDeformer deformer)
    {
        Mesh meshToSave = Instantiate(deformer.DeformedMesh);
        
        string path = EditorUtility.SaveFilePanelInProject(
            "Save Deformed Mesh",
            deformer.OriginalMesh.name + "_RBF",
            "asset",
            "Please enter a file name"
        );

        if (string.IsNullOrEmpty(path)) return;

        AssetDatabase.CreateAsset(meshToSave, path);
        AssetDatabase.SaveAssets();
        
        Debug.Log($"Saved mesh to: {path}");
    }

    void AddBlendShapeToOriginal(RBFDeformer deformer)
    {
        Mesh original = deformer.OriginalMesh;
        Mesh deformed = deformer.DeformedMesh;

        Vector3[] origVerts = original.vertices;
        Vector3[] defVerts = deformed.vertices;
        
        if (origVerts.Length != defVerts.Length)
        {
            Debug.LogError("Vertex count mismatch between original and deformed mesh. Cannot create BlendShape.");
            return;
        }
        
        // 差分計算
        Vector3[] delta = new Vector3[origVerts.Length];
        for (int i = 0; i < origVerts.Length; i++)
        {
            delta[i] = defVerts[i] - origVerts[i];
        }

        string path = EditorUtility.SaveFilePanelInProject(
            "Save BlendShape Mesh",
            original.name + "_BlendShape",
            "asset",
            "Save new mesh"
        );

        if (string.IsNullOrEmpty(path)) return;

        Mesh newMesh = Instantiate(original);
        newMesh.name = Path.GetFileNameWithoutExtension(path);
        // AddBlendShapeFrameは法線と接線の差分をnullで渡すことが可能
        newMesh.AddBlendShapeFrame("RBF_Adjust", 100f, delta, null, null);
        
        AssetDatabase.CreateAsset(newMesh, path);
        AssetDatabase.SaveAssets();

        SkinnedMeshRenderer smr = deformer.GetComponent<SkinnedMeshRenderer>();
        if (smr != null)
        {
            smr.sharedMesh = newMesh;
            // 新しく追加されたブレンドシェイプを即座に100%適用
            smr.SetBlendShapeWeight(newMesh.blendShapeCount - 1, 100f);
        }
        
        Debug.Log($"Created BlendShape mesh at: {path}");
    }
}