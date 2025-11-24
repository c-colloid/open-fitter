# OpenFitter

[English](#english) | [日本語](#japanese)

<a name="english"></a>

An open-source avatar clothing fitting tool compatible with the "MochiFitter" workflow.
Based on the GPL-3 core logic released by Nine Gates, OpenFitter provides a complete pipeline for transferring clothing between different avatar shapes using RBF (Radial Basis Function) deformation and Bone Pose transfer.

***

**Status**: Alpha (Partially Functional)
While the core features for fitting clothing (Mesh Deformation, Bone Transformation, and Re-binding) are implemented and usable, full compatibility with all "MochiFitter" features is not yet achieved.

***

## Features

*   **Blender Tools**:
    *   **Bone Pose Exporter**: Exports the difference between two armatures (Source -> Target) as a JSON file.
    *   **RBF Field Exporter**: Calculates the deformation field between a "Basis" shape key and a "Target" shape key and exports it as RBF data (JSON). Supports epsilon estimation and smoothing.
*   **Unity Tools**:
    *   **OpenFitter Converter**: A standalone Editor Window to convert clothing prefabs.
        *   Applies RBF deformation to meshes.
        *   Applies Bone Pose transformation to the armature.
        *   **Auto Re-binding**: Recalculates BindPoses to ensure the mesh retains its fitted shape without double-deformation artifacts.
        *   **Asset Saving**: Automatically saves deformed meshes and creates a ready-to-use Prefab.

## Installation

### Blender Addon
1.  Copy the `blender_addon` folder (or zip it) and install it in Blender via `Edit > Preferences > Add-ons`.
2.  Enable "Import-Export: OpenFitter Tools".
3.  Access the tools via the **Sidebar (N-Panel) > OpenFitter** tab.

### Unity Package
1.  Copy the `UnityProject/Assets/OpenFitter` folder into your Unity project's `Assets` folder.
2.  Ensure you have the `Newtonsoft Json` package installed (usually included by default in modern Unity versions, or install via Package Manager).

## Usage Workflow

### 1. Blender: Prepare Data
1.  **Bone Data**:
    *   Align your Source Armature to the Target Armature.
    *   Select the Armature and use **OpenFitter > Bone Pose Export** to save `pose_data.json`.
2.  **RBF Data**:
    *   Create a "Basis" shape key (original shape) and a "Target" shape key (fitted shape) on your reference mesh.
    *   Select the mesh and use **OpenFitter > RBF Field Export**.
    *   Select the Basis and Target keys, adjust settings (Epsilon, Smoothing), and export `rbf_data.json`.

### 2. Unity: Convert Clothing
1.  Import the exported `.json` files into your Unity project.
2.  Open **Window > OpenFitter > Converter**.
3.  Assign the **Source Object** (the clothing prefab you want to fit).
4.  Assign the **RBF Data JSON** and **Pose Data JSON**.
5.  Click **Convert & Save**.
6.  A new `[Fitted]` prefab will be created in the output folder, ready for use.

## License

This project is licensed under the GNU General Public License v3.0 (GPL-3).
See the LICENSE file for details.

## Special Thanks

We would like to express our gratitude to Nine Gates for releasing the core logic as open source. Their great contribution to the open source community made this project possible.

## Acknowledgements & Compliance

This software is an independent open-source implementation compatible with "MochiFitter".

* Core Engine: Derived from the GPL-3 licensed source code released by Nine Gates.
* UI & Frontend: Developed entirely from scratch.

Note on Development:
To ensure compliance with the original software's EULA (specifically Article 3), this project was developed without any reverse engineering, decompilation, or disassembly of the proprietary binaries. All original implementations are based solely on public documentation and the GPL-3 source code.

This is an unofficial project and has not received any approval or endorsement from Nine Gates or "MochiFitter".

---

<a name="japanese"></a>

# OpenFitter (日本語)

「もちふぃった～」ワークフローと互換性のある、オープンソースのアバター衣装フィッティングツールです。
Nine Gatesによって公開されたGPL-3コアロジックに基づき、OpenFitterはRBF（放射基底関数）変形とボーンポーズ転送を使用して、異なるアバター形状間で衣装を転送するための完全なパイプラインを提供します。

***

**ステータス**: アルファ（部分的機能動作）
衣装のフィッティングに必要なコア機能（メッシュ変形、ボーン変換、再バインド）は実装されており使用可能ですが、「もちふぃった～」の全機能との完全な互換性はまだ達成されていません。

***

## 機能

*   **Blenderツール**:
    *   **Bone Pose Exporter**: 2つのアーマチュア間（ソース→ターゲット）の差分をJSONファイルとしてエクスポートします。
    *   **RBF Field Exporter**: "Basis"（基準）シェイプキーと "Target"（変形後）シェイプキーの間の変形フィールドを計算し、RBFデータ（JSON）としてエクスポートします。イプシロン推定やスムージングに対応しています。
*   **Unityツール**:
    *   **OpenFitter Converter**: 衣装プレハブを変換するための独立したエディタウィンドウです。
        *   メッシュへのRBF変形の適用
        *   アーマチュアへのボーンポーズ変形の適用
        *   **自動再バインド**: 二重変形によるアーティファクトを防ぎ、メッシュがフィットした形状を維持するようにBindPoseを再計算します。
        *   **アセット保存**: 変形されたメッシュを自動的に保存し、すぐに使用可能なプレハブを作成します。

## インストール

### Blenderアドオン
1.  `blender_addon` フォルダをコピー（またはzip圧縮）し、Blenderの `Edit > Preferences > Add-ons` からインストールします。
2.  "Import-Export: OpenFitter Tools" を有効にします。
3.  **Sidebar (N-Panel) > OpenFitter** タブからツールにアクセスします。

### Unityパッケージ
1.  `UnityProject/Assets/OpenFitter` フォルダを、Unityプロジェクトの `Assets` フォルダ内にコピーします。
2.  `Newtonsoft Json` パッケージがインストールされていることを確認してください（最近のUnityバージョンでは通常デフォルトで含まれていますが、Package Managerからインストールすることも可能です）。

## 使用ワークフロー

### 1. Blender: データの準備
1.  **ボーンデータ**:
    *   ソースアーマチュアをターゲットアーマチュアに位置合わせします。
    *   アーマチュアを選択し、**OpenFitter > Bone Pose Export** を使用して `pose_data.json` を保存します。
2.  **RBFデータ**:
    *   参照メッシュ上で "Basis" シェイプキー（元の形状）と "Target" シェイプキー（フィット後の形状）を作成します。
    *   メッシュを選択し、**OpenFitter > RBF Field Export** を使用します。
    *   BasisキーとTargetキーを選択し、設定（Epsilon, Smoothing）を調整して `rbf_data.json` をエクスポートします。

### 2. Unity: 衣装の変換
1.  エクスポートされた `.json` ファイルをUnityプロジェクトにインポートします。
2.  **Window > OpenFitter > Converter** を開きます。
3.  **Source Object**（フィットさせたい衣装プレハブ）を割り当てます。
4.  **RBF Data JSON** と **Pose Data JSON** を割り当てます。
5.  **Convert & Save** をクリックします。
6.  出力フォルダに新しい `[Fitted]` プレハブが作成され、すぐに使用できます。

## ライセンス

本プロジェクトは GNU General Public License v3.0 (GPL-3) の下で公開されています。
詳細は LICENSE ファイルをご確認ください。

## 謝辞

コアロジックをオープンソースとして公開されたNine Gatesに感謝の意を表します。オープンソースコミュニティへの多大なる貢献により、本プロジェクトの開発が可能となりました。

## クレジット・規約の遵守

本ソフトウェアは「もちふぃった～」と互換性のある、独立したオープンソース実装です。

* コアエンジン: Nine Gatesにより公開されたGPL-3ソースコードを基にしています。
* UI・フロントエンド: 本プロジェクトのために独自に実装されたものです。

開発方針と規約の遵守について:
オリジナル製品の利用規約（特に第三条の禁止事項）を遵守するため、本プロジェクトはプロプライエタリなバイナリに対するリバースエンジニアリング（逆コンパイル、逆アセンブル等）を一切行わずに開発されました。独自実装部分は、公開されているドキュメントおよびGPL-3ソースコードのみを参照しています。

本プロジェクトは非公式なものであり、Nine Gatesおよび「もちふぃった～」からのあらゆる承認、認可等も受けていません。
