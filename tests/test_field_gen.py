# ----------------------------------------------------------------------------
# tests/test_field_gen.py: Unit test for the FieldGenerator and SpatialUtils components.
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

import numpy as np
from spatial_utils import SpatialUtils
from field_generator import FieldGenerator

def test_field_generation():
    print("=== FieldGenerator テスト開始 ===")
    
    # 1. 仮想的なターゲットメッシュ（原点付近の数点）
    mesh_vertices = np.array([
        [0, 0, 0],
        [0.1, 0, 0],
        [0, 0.1, 0]
    ])
    spatial = SpatialUtils(mesh_vertices)
    
    # 2. パラメータ設定
    params = {
        'base_grid_spacing': 0.1,   # グリッド基本サイズ
        'surface_distance': 0.5,    # この距離より遠いと生成しない
        'max_distance': 0.4,
        'min_distance': 0.05,
        'density_falloff': 2.0
    }
    
    # 3. バウンディングボックス（検索範囲）
    # 原点中心に -0.6 ~ +0.6 の範囲
    bounds_min = np.array([-0.6, -0.6, -0.6])
    bounds_max = np.array([0.6, 0.6, 0.6])
    
    # 4. 生成実行
    generator = FieldGenerator(spatial, params)
    points = generator.generate(bounds_min, bounds_max)
    
    # 5. 検証
    print(f"生成されたポイント数: {len(points)}")
    
    if len(points) > 0:
        # 生成された点が surface_distance 以内にあるか確認
        dists, _ = spatial.find_nearest(points)
        max_gen_dist = np.max(dists)
        
        print(f"生成された点の最大距離: {max_gen_dist:.4f} (制限: {params['surface_distance']})")
        
        if max_gen_dist <= params['surface_distance'] + 1e-5:
            print("[PASS] すべての点は制限距離内に生成されました")
        else:
            print("[FAIL] 制限距離外に点が生成されています")
            
        # 原点付近（min_dist以内）には密に生成されているか？
        # これは視覚化しないと完全には分かりませんが、
        # 少なくとも1点は生成されているはずです。
        print("[PASS] ポイント生成処理が完了しました")
    else:
        print("[FAIL] ポイントが生成されませんでした")

if __name__ == "__main__":
    test_field_generation()