# ----------------------------------------------------------------------------
# deformation_pipeline.py: Manages baking deformation fields from a source mesh and applying them to a target mesh.
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

import numpy as np
from rbf_core import RBFCore
from field_generator import FieldGenerator
from spatial_utils import SpatialUtils

class DeformationPipeline:
    """
    ソースメッシュから変形フィールドを生成(Bake)し、
    それをターゲットメッシュに適用(Apply)する一連のフローを管理する。
    """
    
    def __init__(self, params):
        self.params = params
        # RBFのパラメータ
        self.epsilon = params.get('rbf_epsilon', 0.5)
        self.smoothing = params.get('rbf_smoothing', 0.0)
        
    def bake_field(self, source_verts_basis, source_verts_deformed):
        """
        【フェーズ1: Bake】
        ソースメッシュの変形から、空間グリッド(Field)の動きを計算する。
        実際のツールでは、この結果を .npz ファイルに保存する。
        
        Returns:
            dict: フィールドデータ (points, displacements)
        """
        print("--- Pipeline: Baking Field ---")
        
        # 1. フィールド（グリッド点）の生成
        # バウンディングボックスの計算
        bounds_min = np.min(source_verts_basis, axis=0)
        bounds_max = np.max(source_verts_basis, axis=0)
        
        # 少し余裕を持たせる
        margin = self.params.get('bbox_margin', 0.1)
        bounds_min -= margin
        bounds_max += margin
        
        # SpatialUtilsの準備
        spatial = SpatialUtils(source_verts_basis)
        
        # Generatorを使ってグリッド生成
        generator = FieldGenerator(spatial, self.params)
        field_points = generator.generate(bounds_min, bounds_max)
        
        if len(field_points) == 0:
            raise RuntimeError("No field points generated. Check params or mesh size.")
            
        # 2. RBF(1回目): ソースメッシュ → フィールド
        # 「ソースメッシュがこう動くとき、空間上のこの点はどう動くべきか？」を計算
        rbf_1 = RBFCore(epsilon=self.epsilon, smoothing=self.smoothing)
        rbf_1.fit(source_verts_basis, source_verts_deformed)
        
        # フィールド点の変形を予測
        _, field_displacements = rbf_1.predict(field_points)
        
        print(f"Field Baked: {len(field_points)} points")
        
        # この辞書データが、Unityに渡す「軽量化された変形データ」になる
        field_data = {
            'field_points': field_points,            # グリッドの初期位置
            'field_displacements': field_displacements # グリッドの移動量
        }
        return field_data

    def apply_field(self, field_data, target_verts):
        """
        【フェーズ2: Apply】
        ベイクされたフィールドデータを使って、ターゲットメッシュを変形させる。
        Unity/C# で実装するのは「この関数の中身だけ」で良い。
        """
        print("--- Pipeline: Applying Field ---")
        
        field_points = field_data['field_points']
        field_displacements = field_data['field_displacements']
        
        # フィールドの変形後位置
        field_points_deformed = field_points + field_displacements
        
        # 3. RBF(2回目): フィールド → ターゲットメッシュ
        # 「空間グリッドがこう動くなら、その中のターゲットメッシュはどう動く？」
        rbf_2 = RBFCore(epsilon=self.epsilon, smoothing=self.smoothing)
        
        # ここでの「制御点」は、ソースメッシュではなく「フィールド点」になる
        rbf_2.fit(field_points, field_points_deformed)
        
        # ターゲットの変形計算
        target_deformed, target_displacements = rbf_2.predict(target_verts)
        
        return target_deformed, target_displacements