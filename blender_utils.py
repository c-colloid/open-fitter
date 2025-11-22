# ----------------------------------------------------------------------------
# blender_utils.py: Utilities for extracting and injecting data between Blender and NumPy and Blender objects.
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025 tallcat
#
# This program is free software: you can redistribute it and/or modify
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
import numpy as np

class BlenderExtractor:
    """
    Blenderのオブジェクトからデータを抽出し、Numpy配列として提供するクラス。
    """
    
    @staticmethod
    def get_world_vertices(obj, depsgraph=None):
        """
        オブジェクトの頂点をワールド座標系のNumpy配列として取得する。
        モディファイア（アーマチュア等）適用後の状態を取得するためにdepsgraphを使用可能。
        """
        if depsgraph:
            # 評価済み（変形後）のメッシュデータを取得
            eval_obj = obj.evaluated_get(depsgraph)
            mesh = eval_obj.data
        else:
            mesh = obj.data

        # 頂点数を取得
        num_verts = len(mesh.vertices)
        
        # Numpy配列用のバッファを確保 (N, 3)
        verts_co = np.zeros((num_verts, 3), dtype=np.float32)
        
        # 高速に座標をコピー (foreach_getはPythonのforループより遥かに速い)
        mesh.vertices.foreach_get("co", verts_co.ravel())
        
        # ローカル座標 → ワールド座標 変換
        # 行列計算もNumpyで行うため、行列をNumpy配列に変換
        
        # BlenderのMatrixから成分を抽出
        mat = obj.matrix_world
        loc = np.array([mat[0][3], mat[1][3], mat[2][3]])
        
        # 回転・スケール成分 (3x3)
        rot_scale = np.array([
            [mat[0][0], mat[0][1], mat[0][2]],
            [mat[1][0], mat[1][1], mat[1][2]],
            [mat[2][0], mat[2][1], mat[2][2]]
        ])
        
        # 座標変換: V_world = V_local @ RotScale.T + Location
        world_verts = verts_co @ rot_scale.T + loc
        
        return world_verts

    @staticmethod
    def get_shape_key_vertices(obj, key_name):
        """
        特定のシェイプキーの頂点座標（ローカル）を取得する
        """
        if not obj.data.shape_keys or key_name not in obj.data.shape_keys.key_blocks:
            raise ValueError(f"Shape key '{key_name}' not found.")
            
        key_block = obj.data.shape_keys.key_blocks[key_name]
        num_verts = len(key_block.data)
        verts = np.zeros((num_verts, 3), dtype=np.float32)
        key_block.data.foreach_get("co", verts.ravel())
        
        return verts

    @staticmethod
    def set_shape_key_value(obj, key_name, value):
        """シェイプキーの値を設定し、シーンを更新する"""
        if obj.data.shape_keys and key_name in obj.data.shape_keys.key_blocks:
            obj.data.shape_keys.key_blocks[key_name].value = value
            
class BlenderInjector:
    """
    計算結果をBlenderのオブジェクトに適用するクラス。
    """
    
    @staticmethod
    def create_or_update_shape_key(target_obj, displacements_world, key_name="RBF_Result"):
        """
        ワールド座標系の変位量を、ターゲットオブジェクトのシェイプキーとして適用する。
        
        Parameters:
            target_obj: 適用対象のBlenderオブジェクト
            displacements_world: ワールド座標系での変位量 (N, 3) numpy array
            key_name: シェイプキー名
        """
        # ベースシェイプキーがない場合は作成
        if not target_obj.data.shape_keys:
            target_obj.shape_key_add(name="Basis")
            
        # 対象のシェイプキーを取得または作成
        if key_name in target_obj.data.shape_keys.key_blocks:
            key_block = target_obj.data.shape_keys.key_blocks[key_name]
        else:
            key_block = target_obj.shape_key_add(name=key_name)
            
        # ワールド変位 → ローカル座標への変換
        # Vector_Local = World_Matrix_Inv_3x3 @ Vector_World
        
        mat_inv = target_obj.matrix_world.inverted()
        
        # 行列の回転・スケール成分の逆行列 (3x3)
        rot_scale_inv = np.array([
            [mat_inv[0][0], mat_inv[0][1], mat_inv[0][2]],
            [mat_inv[1][0], mat_inv[1][1], mat_inv[1][2]],
            [mat_inv[2][0], mat_inv[2][1], mat_inv[2][2]]
        ])
        
        # 変位ベクトルをローカル空間に変換
        displacements_local = displacements_world @ rot_scale_inv.T
        
        # 現在のBasis（変形前）の座標を取得
        basis_verts = np.zeros((len(target_obj.data.vertices), 3), dtype=np.float32)
        target_obj.data.vertices.foreach_get("co", basis_verts.ravel())
        
        # 新しい座標 = Basis + Local_Displacement
        new_coords = basis_verts + displacements_local
        
        # シェイプキーに書き込み
        key_block.data.foreach_set("co", new_coords.ravel())
        
        # シェイプキーを有効化して見えるようにする
        key_block.value = 1.0
        print(f"Shape key '{key_name}' updated.")