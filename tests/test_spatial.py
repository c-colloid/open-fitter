# ----------------------------------------------------------------------------
# tests/test_spatial.py: Unit test for `SpatialUtils` covering nearest-neighbor and distance-filtering behavior.
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

def test_spatial_query():
    print("=== SpatialUtils テスト開始 ===")
    
    # 1. ターゲットとなるメッシュ（のような点群）
    # 原点にある1点だけを定義してみる
    mesh_vertices = np.array([[0, 0, 0]])
    
    spatial = SpatialUtils(mesh_vertices)
    
    # 2. 検索点（原点から距離 2.0 の点）
    query_point = np.array([[0, 2.0, 0]])
    
    # 3. 距離計算テスト
    dists, idxs = spatial.find_nearest(query_point)
    
    print(f"距離: {dists[0]} (期待値: 2.0)")
    
    if np.isclose(dists[0], 2.0):
        print("[PASS] 距離計算は正常です")
    else:
        print("[FAIL] 距離計算が誤っています")

    # 4. フィルタリングテスト (max_dist=1.0 なら除外されるはず)
    filtered, mask = spatial.filter_points_by_distance(query_point, max_distance=1.0)
    if len(filtered) == 0:
        print("[PASS] 距離フィルタリング(除外)は正常です")
    else:
        print("[FAIL] 距離フィルタリングで除外されるべき点が残っています")

if __name__ == "__main__":
    test_spatial_query()