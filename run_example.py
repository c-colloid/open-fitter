# ----------------------------------------------------------------------------
# run_example.py: Example script that builds a test scene in Blender, runs the deformation pipeline, and exports results.
# Copyright (C) [2025] tallcat
#
# This file is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This file is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the accompanying LICENSE file for more details.
# ----------------------------------------------------------------------------

import bpy
import sys
import os
import numpy as np
import json
import importlib

# --- 1. Path setup ---
blend_dir = os.path.dirname(bpy.data.filepath)
if not blend_dir:
    print("エラー: 先に.blendファイルを保存してください！")
else:
    if blend_dir not in sys.path:
        sys.path.append(blend_dir)

# --- 2. モジュール読み込み ---
import rbf_core
import spatial_utils
import field_generator
import deformation_pipeline
import blender_utils

importlib.reload(rbf_core)
importlib.reload(spatial_utils)
importlib.reload(field_generator)
importlib.reload(deformation_pipeline)
importlib.reload(blender_utils)

from deformation_pipeline import DeformationPipeline
from rbf_core import RBFCore
from blender_utils import BlenderExtractor, BlenderInjector

def run_full_test():
    print("\n=== MochiFitter 統合テスト & エクスポート ===")

    # ---------------------------------------------------------
    # A. シーンセットアップ
    # ---------------------------------------------------------
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    # Source Cube
    bpy.ops.mesh.primitive_cube_add(size=2)
    source_obj = bpy.context.active_object
    source_obj.name = "SourceCube"
    source_obj.shape_key_add(name="Basis")
    key1 = source_obj.shape_key_add(name="DeformKey")
    
    for i in range(len(key1.data)):
        co = key1.data[i].co
        if co.z > 0.1:
            key1.data[i].co = (co.x * 1.5, co.y * 1.5, co.z + 2.0)

    # Target Sphere
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5)
    target_obj = bpy.context.active_object
    target_obj.name = "TargetSphere"

    print("シーン作成完了")

    # ---------------------------------------------------------
    # B. データ抽出
    # ---------------------------------------------------------
    depsgraph = bpy.context.evaluated_depsgraph_get()

    BlenderExtractor.set_shape_key_value(source_obj, "DeformKey", 0.0)
    depsgraph.update()
    src_basis = BlenderExtractor.get_world_vertices(source_obj, depsgraph)

    BlenderExtractor.set_shape_key_value(source_obj, "DeformKey", 1.0)
    depsgraph.update()
    src_deformed = BlenderExtractor.get_world_vertices(source_obj, depsgraph)

    # ターゲットの頂点も取得（適用計算のため）
    tgt_verts = BlenderExtractor.get_world_vertices(target_obj, depsgraph)

    # ---------------------------------------------------------
    # C. パイプライン実行
    # ---------------------------------------------------------
    params = {
        'base_grid_spacing': 0.3,
        'surface_distance': 2.0,
        'max_distance': 2.5,
        'min_distance': 0.05,
        'density_falloff': 3.0,
        'rbf_epsilon': 0.5,
        'bbox_margin': 0.5
    }

    pipeline = DeformationPipeline(params)
    
    # 1. Bake
    field_data = pipeline.bake_field(src_basis, src_deformed)
    field_points = field_data['field_points']
    
    print(f"フィールド生成完了: {len(field_points)} 点")

    # ---------------------------------------------------------
    # C.5 結果の適用 (Blender確認用: ここを追加しました)
    # ---------------------------------------------------------
    print("Blender上で変形結果を適用中...")
    
    # Apply計算
    tgt_deformed, tgt_disps = pipeline.apply_field(field_data, tgt_verts)
    
    # シェイプキー書き込み (Injector)
    BlenderInjector.create_or_update_shape_key(target_obj, tgt_disps, "RBF_Result")

    # ---------------------------------------------------------
    # D. Unity用データの計算 & エクスポート
    # ---------------------------------------------------------
    print("Unity用データを準備中...")
    field_disps = field_data['field_displacements']
    field_deformed = field_points + field_disps
    
    rbf_for_unity = RBFCore(epsilon=params['rbf_epsilon'])
    rbf_for_unity.fit(field_points, field_deformed)

    # JSON保存
    export_data = {
        "epsilon": rbf_for_unity.epsilon,
        "centers": field_points.tolist(),
        "weights": rbf_for_unity.weights.tolist(),
        "poly_weights": rbf_for_unity.polynomial_weights.tolist()
    }
    
    json_path = os.path.join(blend_dir, "rbf_data.json")
    with open(json_path, 'w') as f:
        json.dump(export_data, f)

    # FBX保存 (シェイプキーがついた状態で保存されるのでUnityでも確認しやすい)
    bpy.ops.object.select_all(action='DESELECT')
    target_obj.select_set(True)
    bpy.context.view_layer.objects.active = target_obj
    
    fbx_path = os.path.join(blend_dir, "TargetSphere.fbx")
    bpy.ops.export_scene.fbx(
        filepath=fbx_path,
        use_selection=True,
        object_types={'MESH'},
        axis_forward='-Z',
        axis_up='Y',
        apply_scale_options='FBX_SCALE_ALL',
        mesh_smooth_type='FACE',
        bake_anim=False
    )
    
    print(f"保存完了: {json_path}")
    print(f"保存完了: {fbx_path}")
    print("=== 全工程完了 ===")

if __name__ == "__main__":
    run_full_test()