# ----------------------------------------------------------------------------
# tests/unity_export.py: Exports Unity-compatible RBF data and target mesh for verification in Unity.
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
import json
import numpy as np
import os
import sys

# Path setup (append blend file directory to sys.path)
blend_dir = os.path.dirname(bpy.data.filepath)
if blend_dir not in sys.path:
    sys.path.append(blend_dir)

import rbf_core
import deformation_pipeline
import blender_utils
from rbf_core import RBFCore
from deformation_pipeline import DeformationPipeline
from blender_utils import BlenderExtractor

def export_for_unity():
    print("=== Unity向けデータのエクスポート開始 ===")
    
    # 1. シーンからデータを取得 (直前のテストと同じ設定)
    source_obj = bpy.data.objects.get("SourceCube")
    target_obj = bpy.data.objects.get("TargetSphere")
    
    if not source_obj or not target_obj:
        print("エラー: SourceCube または TargetSphere が見つかりません。")
        print("直前の pipeline_test() を実行してシーンを作ってください。")
        return

    depsgraph = bpy.context.evaluated_depsgraph_get()
    
    # Basis状態
    BlenderExtractor.set_shape_key_value(source_obj, "DeformKey", 0.0)
    depsgraph.update()
    src_basis = BlenderExtractor.get_world_vertices(source_obj, depsgraph)
    
    # Deformed状態
    BlenderExtractor.set_shape_key_value(source_obj, "DeformKey", 1.0)
    depsgraph.update()
    src_deformed = BlenderExtractor.get_world_vertices(source_obj, depsgraph)
    
    # 2. パイプラインで計算 (Bake)
    params = {
        'base_grid_spacing': 0.4, # JSONサイズ削減のため少し粗めに
        'surface_distance': 2.0,
        'max_distance': 2.5,
        'min_distance': 0.05,
        'density_falloff': 3.0,
        'rbf_epsilon': 0.5,
        'bbox_margin': 0.5
    }
    
    pipeline = DeformationPipeline(params)
    field_data = pipeline.bake_field(src_basis, src_deformed)
    
    field_points = field_data['field_points']
    field_disps = field_data['field_displacements']
    field_deformed = field_points + field_disps
    
    # 3. 【重要】ここが最適化ポイント
    # Unityでやるはずだった "Fit" をここで実行してしまう
    print("Pre-calculating RBF weights for Unity...")
    rbf = RBFCore(epsilon=params['rbf_epsilon'])
    rbf.fit(field_points, field_deformed)
    
    # 4. JSONに保存
    # Unityが必要とするのは「制御点(Centers)」と「重み(Weights)」だけ
    export_data = {
        "epsilon": rbf.epsilon,
        "centers": field_points.tolist(),           # List[List[float]]
        "weights": rbf.weights.tolist(),            # List[List[float]]
        "poly_weights": rbf.polynomial_weights.tolist() # List[List[float]]
    }
    
    # 出力パス (Blendファイルと同じ場所)
    output_path = os.path.join(blend_dir, "rbf_data.json")
    
    with open(output_path, 'w') as f:
        json.dump(export_data, f)
        
    print(f"エクスポート完了: {output_path}")
    print(f"制御点数: {len(field_points)}")

    # ターゲットメッシュもOBJとして書き出す（Unityでの確認用）
    # (TargetSphereを選択してエクスポート)
    bpy.ops.object.select_all(action='DESELECT')
    target_obj.select_set(True)
    bpy.context.view_layer.objects.active = target_obj
    obj_path = os.path.join(blend_dir, "TargetSphere.obj")
    bpy.ops.wm.obj_export(filepath=obj_path, export_selected_objects=True)
    print(f"ターゲットメッシュ出力: {obj_path}")

if __name__ == "__main__":
    export_for_unity()