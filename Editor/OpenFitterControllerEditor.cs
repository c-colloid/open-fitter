// ----------------------------------------------------------------------------
// Copyright (C) [2025] tallcat
//
// This file is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This file is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
// See the accompanying LICENSE file for more details.
// ----------------------------------------------------------------------------

using UnityEngine;
using UnityEditor;
using UnityEditor.UIElements;
using UnityEngine.UIElements;

[CustomEditor(typeof(OpenFitterController))]
public class OpenFitterControllerEditor : Editor
{
	[SerializeField] VisualTreeAsset UI;
	OpenFitterController controller;
	
	// This function is called when the object is loaded.
	internal void OnEnable() {
		if (controller != null) return;
		controller = (OpenFitterController)target;
	}
	
	public override VisualElement CreateInspectorGUI() {
		var root = new VisualElement();
		UI.CloneTree(root);
		
		root.Q<Button>("RunFullFittingPipeline").clicked += OnClickRunFullFittingPipelineButton;
		root.Q<Button>("ResetBonePose").clicked += OnClickResetBonePoseButton;
		
		return root;
	}
	
	void OnClickRunFullFittingPipelineButton()
	{
		Undo.RecordObjects(controller.GetComponentsInChildren<Transform>(true), "Run OpenFitter Pipeline");
		controller.RunFullFittingPipeline();
		SceneView.RepaintAll();
	}
	
	void OnClickResetBonePoseButton()
	{
		controller.ResetAll();
		SceneView.RepaintAll();
	}
	
    public override void OnInspectorGUI()
    {
        DrawDefaultInspector();

        OpenFitterController controller = (OpenFitterController)target;

        GUILayout.Space(20);
        GUILayout.Label("Pipeline Execution", EditorStyles.boldLabel);

        GUI.backgroundColor = new Color(0.7f, 1.0f, 0.7f);
        if (GUILayout.Button("Run Full Fitting Pipeline", GUILayout.Height(40)))
        {
	        OnClickRunFullFittingPipelineButton();
        }
        GUI.backgroundColor = Color.white;

        GUILayout.Space(10);
        if (GUILayout.Button("Reset Bone Pose"))
        {
	        OnClickResetBonePoseButton();
        }
    }
}
