# ----------------------------------------------------------------------------
# field_generator.py: Generates adaptive-density control points for a deformation field based on bounding box and distance field.
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
from math import ceil, sqrt
import time

class FieldGenerator:
    """
    Generates adaptive-density control points (deformation field) within a bounding box using distance queries.
    """

    def __init__(self, spatial_utils, params):
        """
        Parameters:
            spatial_utils: SpatialUtilsのインスタンス（距離計算用）
            params: 設定値辞書 (spacing, surface_dist, max_dist, min_dist, falloff)
        """
        self.spatial = spatial_utils
        
        # パラメータの展開
        self.base_spacing = params.get('base_grid_spacing', 0.02)
        self.surface_dist = params.get('surface_distance', 0.1)
        self.max_dist = params.get('max_distance', 0.2)
        self.min_dist = params.get('min_distance', 0.005)
        self.density_falloff = params.get('density_falloff', 3.0)
        
        # 計算用キャッシュ
        self.inv_max_min_diff = 1.0 / (self.max_dist - self.min_dist) if self.max_dist > self.min_dist else 1.0
        self.spacing_cache = {}
        self.generated_points = []

    def _get_adaptive_spacing(self, distance):
        """距離に応じたグリッド間隔レベル（2^n）を計算"""
        if distance <= self.min_dist:
            return 0
        elif distance > self.surface_dist:
            return float('inf')
        else:
            normalized_dist = (distance - self.min_dist) * self.inv_max_min_diff
            normalized_dist = min(1.0, max(0.0, normalized_dist))
            
            power = sqrt(normalized_dist) * self.density_falloff
            level = int(power + 1)
            # 2^level を返す（ビットシフト）
            return 1 << level

    def _process_cell(self, x_start, y_start, z_start, cell_size, level=0, max_level=3):
        """
        再帰的にセルを分割・評価する関数
        grid_spacing単位での座標系を使用
        """
        # セルの8頂点のワールド座標を生成
        # (簡略化のため、セルの中心と対角点などで簡易判定する場合もあるが、
        #  元のロジックに忠実に8点チェックを行う)
        check_points = []
        for dx in [0, 1]:
            for dy in [0, 1]:
                for dz in [0, 1]:
                    px = x_start + dx * cell_size * self.base_spacing
                    py = y_start + dy * cell_size * self.base_spacing
                    pz = z_start + dz * cell_size * self.base_spacing
                    check_points.append([px, py, pz])
        
        check_points_np = np.array(check_points)
        
        # SpatialUtilsを使って距離を一括計算
        dists, _ = self.spatial.find_nearest(check_points_np)
        min_dist_in_cell = np.min(dists)
        
        # 範囲外なら打ち切り
        if min_dist_in_cell > self.surface_dist:
            return

        # 適応的間隔の計算
        adaptive_spacing = self._get_adaptive_spacing(min_dist_in_cell)
        
        # 分割判定: 現在のセルサイズが適応サイズより大きく、かつ最大レベル未満なら分割
        if cell_size > adaptive_spacing and level < max_level:
            half_size = cell_size // 2
            if half_size > 0:
                for dx in [0, 1]:
                    for dy in [0, 1]:
                        for dz in [0, 1]:
                            nx = x_start + dx * half_size * self.base_spacing
                            ny = y_start + dy * half_size * self.base_spacing
                            nz = z_start + dz * half_size * self.base_spacing
                            self._process_cell(nx, ny, nz, half_size, level + 1, max_level)
            return

        # ポイント生成（セルの中心）
        cx = x_start + (cell_size * self.base_spacing) / 2
        cy = y_start + (cell_size * self.base_spacing) / 2
        cz = z_start + (cell_size * self.base_spacing) / 2
        
        # 生成する点の距離を最終確認
        center_point = np.array([[cx, cy, cz]])
        dist, _ = self.spatial.find_nearest(center_point)
        
        if dist[0] <= self.surface_dist:
            self.generated_points.append([cx, cy, cz])

    def generate(self, bounds_min, bounds_max):
        """
        指定されたバウンディングボックス内でポイント生成を実行
        """
        self.generated_points = []
        self.spacing_cache = {}
        
        # 初期セルサイズの決定
        max_level = int(self.density_falloff + 1)
        initial_cell_size = 1 << max_level # 2^max_level
        
        # グリッドループ範囲の計算
        # bounds_min/max は numpy array を想定
        start_coords = bounds_min
        dimensions = bounds_max - bounds_min
        
        steps_x = int(ceil(dimensions[0] / self.base_spacing)) + 1
        steps_y = int(ceil(dimensions[1] / self.base_spacing)) + 1
        steps_z = int(ceil(dimensions[2] / self.base_spacing)) + 1
        
        print(f"Grid generation start. Initial cell size: {initial_cell_size}")
        start_time = time.time()

        print(f"Grid generation start. Initial cell size: {initial_cell_size}")
        print(f"Bounds: {bounds_min} to {bounds_max}") # 追加
        print(f"Spacing: {self.base_spacing}, SurfaceDist: {self.surface_dist}") # 追加
        
        # 粗いグリッドで走査開始
        for z in range(0, steps_z, initial_cell_size):
            z_pos = start_coords[2] + z * self.base_spacing
            for y in range(0, steps_y, initial_cell_size):
                y_pos = start_coords[1] + y * self.base_spacing
                for x in range(0, steps_x, initial_cell_size):
                    x_pos = start_coords[0] + x * self.base_spacing
                    
                    # 再帰処理開始
                    self._process_cell(x_pos, y_pos, z_pos, initial_cell_size, 0, max_level)
                    
        elapsed = time.time() - start_time
        print(f"Generated {len(self.generated_points)} points in {elapsed:.4f} sec")
        
        return np.array(self.generated_points)