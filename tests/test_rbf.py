# ----------------------------------------------------------------------------
# tests/test_rbf.py: Unit test for `RBFCore` to verify weight computation and interpolation behavior.
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
from rbf_core import RBFCore

def test_rbf_basic_logic():
    print("=== RBFCore 単体テスト開始 ===")

    # 1. テストデータの作成 (単純な立方体の頂点)
    # サイズ 1.0 の立方体の8頂点を「制御点」とします
    source_points = np.array([
        [0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1],
        [1, 1, 0], [1, 0, 1], [0, 1, 1], [1, 1, 1]
    ], dtype=float)

    # 2. 変形後の定義 (X軸方向に +1.0 移動させる単純な平行移動)
    # 本来RBFはもっと複雑な変形に使いますが、テストのため単純化します
    target_points = source_points + np.array([1.0, 0.0, 0.0])

    # 3. RBFCoreの初期化
    rbf = RBFCore(epsilon=0.5, smoothing=0.0)

    # 4. 計算実行 (Fit)
    print("Calculing weights...")
    rbf.fit(source_points, target_points)

    # --- 検証1: 制御点自身の再現性チェック ---
    # 制御点自身を入力したら、target_points と完全に一致するはずです
    print("Test 1: Checking Control Points reproduction...")
    predicted_targets, _ = rbf.predict(source_points)
    
    # 誤差が非常に小さいか確認 (allclose は np.abs(a - b) < tolerance を判定)
    if np.allclose(predicted_targets, target_points, atol=1e-5):
        print("[PASS] 制御点の位置は正確に再現されました。")
    else:
        print("[FAIL] 制御点の位置がズレています！")
        print("差分最大値:", np.max(np.abs(predicted_targets - target_points)))

    # --- 検証2: 中間地点の補間チェック ---
    # 立方体の中心 [0.5, 0.5, 0.5] も、Xに +1.0 移動して [1.5, 0.5, 0.5] になるはず
    print("Test 2: Checking Interpolation (Middle point)...")
    test_point = np.array([[0.5, 0.5, 0.5]])
    expected_point = np.array([[1.5, 0.5, 0.5]])
    
    predicted_test, _ = rbf.predict(test_point)
    
    # 平行移動のような単純変形の場合、RBFはほぼ正確に追従します
    if np.allclose(predicted_test, expected_point, atol=1e-2):
        print(f"[PASS] 中間地点の補間も正常です。 {predicted_test[0]}")
    else:
        print(f"[FAIL] 中間地点の挙動がおかしいです。")
        print(f"予想: {expected_point[0]}, 結果: {predicted_test[0]}")

    print("=== テスト終了 ===")

if __name__ == "__main__":
    test_rbf_basic_logic()