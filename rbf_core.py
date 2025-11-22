# ----------------------------------------------------------------------------
# rbf_core.py: Core RBF (radial basis function) interpolation implementation used for computing weights and predicting deformations.
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

# SciPy import for distance computations (optional; ImportError is passed to caller)
try:
    from scipy.spatial.distance import cdist
except ImportError:
    pass

class RBFCore:
    """
    RBF（放射基底関数）補間の計算のみを担当するクラス。
    Blender(bpy)やmathutilsには一切依存しない。
    UnityのC#コードに移植する際の直接のモデルとなる。
    """

    def __init__(self, epsilon=1.0, smoothing=0.0):
        self.epsilon = epsilon
        self.smoothing = smoothing
        # 計算結果の重み（C#移植時はこれを保存・ロードすることになる）
        self.weights = None
        self.polynomial_weights = None
        self.control_points = None
    
    def _kernel_func(self, r):
        """Multi-Quadratic Biharmonic RBFカーネル関数"""
        # Unity(Shader/C#)での実装時は: sqrt(r*r + epsilon*epsilon)
        return np.sqrt(r**2 + self.epsilon**2)

    def fit(self, source_points, target_points):
        """
        制御点の移動量からRBFの重みを計算する（連立方程式を解く）。
        
        Parameters:
            source_points (np.ndarray): 変形前の制御点座標 (N, 3)
            target_points (np.ndarray): 変形後の制御点座標 (N, 3)
        """
        # 変位ベクトル (Displacements)
        displacements = target_points - source_points
        self.control_points = source_points
        
        num_pts, dim = source_points.shape
        
        # 距離行列の計算
        dists = cdist(source_points, source_points)
        
        # カーネル行列 (Phi)
        phi = self._kernel_func(dists)
        
        # 正則化（スムージング）
        if self.smoothing > 0:
            phi += np.eye(num_pts) * self.smoothing

        # 多項式項のための行列 P (1, x, y, z)
        P = np.ones((num_pts, dim + 1))
        P[:, 1:] = source_points
        
        # 線形システムの構築
        # | Phi  P | | weights |   | displacements |
        # | P.T  0 | | poly_w  | = |       0       |
        
        A = np.zeros((num_pts + dim + 1, num_pts + dim + 1))
        A[:num_pts, :num_pts] = phi
        A[:num_pts, num_pts:] = P
        A[num_pts:, :num_pts] = P.T
        
        # 右辺 (b)
        b = np.zeros((num_pts + dim + 1, dim))
        b[:num_pts] = displacements
        
        # 方程式を解く (Ax = b)
        try:
            x = np.linalg.solve(A, b)
        except np.linalg.LinAlgError:
            # 特異行列対策（疑似逆行列）
            # Unityで実装する際もSVDなどを用いた対策が必要になる箇所
            reg = np.eye(A.shape[0]) * 1e-6
            x = np.linalg.lstsq(A + reg, b, rcond=None)[0]
            
        # 重みの保存
        self.weights = x[:num_pts]
        self.polynomial_weights = x[num_pts:]

    def predict(self, mesh_vertices):
        """
        計算された重みを使って、任意のメッシュ頂点を変形させる。
        
        Parameters:
            mesh_vertices (np.ndarray): 変形対象の頂点座標 (M, 3)
            
        Returns:
            np.ndarray: 変形後の頂点座標 (M, 3)
            np.ndarray: 変位量 (M, 3)
        """
        if self.weights is None:
            raise RuntimeError("RBF weights not computed. Call fit() first.")

        num_verts, dim = mesh_vertices.shape
        
        # ターゲット頂点と制御点の間の距離
        dists = cdist(mesh_vertices, self.control_points)
        phi = self._kernel_func(dists)
        
        # 多項式項
        P = np.ones((num_verts, dim + 1))
        P[:, 1:] = mesh_vertices
        
        # 変位の計算: Sum(w * phi(r)) + Poly(x)
        displacements = np.dot(phi, self.weights) + np.dot(P, self.polynomial_weights)
        
        deformed_vertices = mesh_vertices + displacements
        
        return deformed_vertices, displacements