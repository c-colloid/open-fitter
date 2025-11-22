# ----------------------------------------------------------------------------
# spatial_utils.py: Spatial lookup utilities (KD-tree queries) for nearest neighbor and distance computations.
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
try:
    from scipy.spatial import cKDTree
except ImportError:
    pass

class SpatialUtils:
    """
    Handles spatial queries (nearest neighbor and distance computations) via a KD-tree.
    """
    
    def __init__(self, vertices):
        """
        Parameters:
            vertices (np.ndarray): メッシュ等の頂点座標群 (N, 3)
        """
        self.tree = cKDTree(vertices)
    
    def find_nearest(self, query_points):
        """
        指定された点群に対して、最も近い頂点との距離とインデックスを返す。
        
        Parameters:
            query_points (np.ndarray): 検索したい点群 (M, 3)
            
        Returns:
            distances (np.ndarray): 最近傍点までの距離 (M,)
            indices (np.ndarray): 最近傍点のインデックス (M,)
        """
        # cKDTree.query は (distance, index) を返す
        # k=1 は「最も近い1点」を探すという意味
        distances, indices = self.tree.query(query_points, k=1)
        return distances, indices

    def filter_points_by_distance(self, query_points, max_distance):
        """
        特定距離以内にある点だけを抽出する（Deformation Field生成等で使用）
        """
        distances, _ = self.find_nearest(query_points)
        mask = distances <= max_distance
        return query_points[mask], mask