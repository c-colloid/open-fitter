bl_info = {
    "name": "OpenFitter RBF Exporter",
    "author": "OpenFitter",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar > OpenFitter",
    "description": "Exports RBF deformation field from Shape Keys to JSON.",
    "category": "Import-Export",
}

import bpy
import json
import numpy as np
import os
import time

# ------------------------------------------------------------------------
# RBF Core Implementation (Embedded for portability)
# ------------------------------------------------------------------------

class RBFCore:
    """
    RBF (Radial Basis Function) interpolation core.
    Uses Multi-Quadratic Biharmonic Kernel: sqrt(r^2 + epsilon^2)
    """

    def __init__(self, epsilon=1.0, smoothing=0.0):
        self.epsilon = epsilon
        self.smoothing = smoothing
        self.weights = None
        self.polynomial_weights = None
        self.control_points = None
    
    def _kernel_func(self, r):
        return np.sqrt(r**2 + self.epsilon**2)

    def fit(self, source_points, target_points):
        """
        Fits the RBF to the source -> target deformation.
        source_points: (N, 3)
        target_points: (N, 3)
        """
        displacements = target_points - source_points
        self.control_points = source_points
        
        num_pts, dim = source_points.shape
        
        # Calculate distance matrix (using numpy broadcasting)
        # dists[i, j] = distance(source[i], source[j])
        # Memory efficient way for larger N might be needed, but for N=3000 it's fine (~80MB)
        d1 = source_points[:, np.newaxis, :]
        d2 = source_points[np.newaxis, :, :]
        dists = np.sqrt(np.sum((d1 - d2)**2, axis=2))
        
        # Kernel Matrix (Phi)
        phi = self._kernel_func(dists)
        
        # Smoothing
        if self.smoothing > 0:
            phi += np.eye(num_pts) * self.smoothing

        # Polynomial Matrix P (1, x, y, z)
        P = np.ones((num_pts, dim + 1))
        P[:, 1:] = source_points
        
        # Build System Matrix A
        # | Phi  P |
        # | P.T  0 |
        
        A_top = np.hstack([phi, P])
        A_bot = np.hstack([P.T, np.zeros((dim + 1, dim + 1))])
        A = np.vstack([A_top, A_bot])
        
        # RHS b
        # | displacements |
        # |       0       |
        
        b = np.zeros((num_pts + dim + 1, dim))
        b[:num_pts] = displacements
        
        # Solve Ax = b
        try:
            x = np.linalg.solve(A, b)
        except np.linalg.LinAlgError:
            # Fallback to least squares if singular
            reg = np.eye(A.shape[0]) * 1e-6
            x = np.linalg.lstsq(A + reg, b, rcond=None)[0]
            
        self.weights = x[:num_pts]
        self.polynomial_weights = x[num_pts:]

# ------------------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------------------

def extract_vertices(key_block):
    num_verts = len(key_block.data)
    verts = np.zeros((num_verts, 3), dtype=np.float32)
    key_block.data.foreach_get("co", verts.ravel())
    return verts

def filter_significant_points(centers, deltas, threshold=0.0001):
    mags = np.linalg.norm(deltas, axis=1)
    mask = mags > threshold
    return centers[mask], deltas[mask], mask

def apply_x_mirror(centers, deltas):
    # Mirror points with X > epsilon (positive side)
    mirror_mask = centers[:, 0] > 0.0001
    mirror_centers = centers[mirror_mask].copy()
    mirror_deltas = deltas[mirror_mask].copy()
    
    mirror_centers[:, 0] *= -1
    mirror_deltas[:, 0] *= -1
    
    return np.vstack([centers, mirror_centers]), np.vstack([deltas, mirror_deltas])

def downsample_points(centers, deltas, epsilon, max_points):
    # Grid Sampling
    grid_spacing = max(epsilon * 0.2, 0.001)
    grid = {}
    for i, p in enumerate(centers):
        key = (int(p[0]/grid_spacing), int(p[1]/grid_spacing), int(p[2]/grid_spacing))
        if key not in grid:
            grid[key] = i
    
    indices = list(grid.values())
    indices.sort()
    centers = centers[indices]
    deltas = deltas[indices]
    
    # Random Downsampling
    if len(centers) > max_points:
        np.random.seed(42)
        indices = np.random.choice(len(centers), max_points, replace=False)
        centers = centers[indices]
        deltas = deltas[indices]
        
    return centers, deltas

def calculate_bounds(points, margin, enable_mirror=False):
    # Calculate bounds of the active points
    # If mirror is enabled, we should include the mirrored bounds too
    
    min_b = np.min(points, axis=0)
    max_b = np.max(points, axis=0)
    
    if enable_mirror:
        # If we mirror, the X bounds will be symmetric
        # Max X becomes max(Max X, -Min X)
        # Min X becomes min(Min X, -Max X)
        # But simpler: just mirror the points and check min/max
        mirror_points = points.copy()
        mirror_points[:, 0] *= -1
        
        all_points = np.vstack([points, mirror_points])
        min_b = np.min(all_points, axis=0)
        max_b = np.max(all_points, axis=0)
    
    return (min_b - margin), (max_b + margin)

def fit_rbf_model(centers, targets, epsilon, smoothing):
    rbf = RBFCore(epsilon=epsilon, smoothing=smoothing)
    rbf.fit(centers, targets)
    return rbf

def create_rbf_entry(name, weight, rbf, centers, bounds_min, bounds_max):
    return {
        "name": name,
        "weight": weight,
        "epsilon": float(rbf.epsilon),
        "centers": centers.tolist(),
        "weights": rbf.weights.tolist(),
        "poly_weights": rbf.polynomial_weights.tolist(),
        "bounds_min": bounds_min.tolist(),
        "bounds_max": bounds_max.tolist()
    }

# ------------------------------------------------------------------------
# Blender Operator & Logic
# ------------------------------------------------------------------------

def get_shape_key_names(self, context):
    obj = context.active_object
    if obj and obj.type == 'MESH' and obj.data.shape_keys:
        return [(key.name, key.name, "") for key in obj.data.shape_keys.key_blocks]
    return []

class OPENFITTER_OT_estimate_epsilon(bpy.types.Operator):
    """Estimate optimal Epsilon based on average nearest neighbor distance"""
    bl_idname = "openfitter.estimate_epsilon"
    bl_label = "Estimate Epsilon"
    
    def execute(self, context):
        obj = context.active_object
        props = context.scene.openfitter_rbf_props
        
        if not obj or obj.type != 'MESH' or not obj.data.shape_keys:
            self.report({'ERROR'}, "Select a mesh with shape keys first.")
            return {'CANCELLED'}
            
        basis_name = props.basis_shape_key
        if basis_name not in obj.data.shape_keys.key_blocks:
            self.report({'ERROR'}, "Basis key not found.")
            return {'CANCELLED'}
            
        # Extract vertices
        basis_block = obj.data.shape_keys.key_blocks[basis_name]
        num_verts = len(basis_block.data)
        
        # Optimization: Use a random subset if too many vertices
        sample_size = min(num_verts, 1000)
        np.random.seed(42) # FIX: Deterministic Seed
        indices = np.random.choice(num_verts, sample_size, replace=False)
        
        verts = np.zeros((sample_size, 3), dtype=np.float32)
        # foreach_get doesn't support indices, so we have to get all and slice, or loop.
        # Getting all is faster in Python.
        all_verts = np.zeros((num_verts * 3), dtype=np.float32)
        basis_block.data.foreach_get("co", all_verts)
        all_verts = all_verts.reshape((-1, 3))
        verts = all_verts[indices]
        
        # Calculate average nearest neighbor distance
        # Brute force for 1000 points is 1M comparisons, fast enough.
        d1 = verts[:, np.newaxis, :]
        d2 = verts[np.newaxis, :, :]
        dists = np.sqrt(np.sum((d1 - d2)**2, axis=2))
        
        # Mask diagonal (self-distance 0)
        np.fill_diagonal(dists, np.inf)
        
        min_dists = np.min(dists, axis=1)
        avg_dist = np.mean(min_dists)
        
        # Heuristic: Epsilon should be around the average spacing.
        # A bit larger to ensure overlap.
        estimated = avg_dist * 1.5
        
        props.epsilon = estimated
        self.report({'INFO'}, f"Estimated Epsilon: {estimated:.4f} (Avg Dist: {avg_dist:.4f})")
        
        return {'FINISHED'}

class OPENFITTER_OT_export_rbf_json(bpy.types.Operator):
    """Export RBF Field to JSON based on active object's shape keys"""
    bl_idname = "openfitter.export_rbf_json"
    bl_label = "Export RBF JSON"
    
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    
    def create_adaptive_deformation_field(self, source_points, target_points, epsilon, smoothing, max_points=1000, error_threshold=0.001):
        """
        Creates an adaptive deformation field using Greedy Selection.
        Selects a subset of source_points that best approximates the deformation.
        """
        print(f"Starting Adaptive RBF Fitting (Max Points: {max_points}, Threshold: {error_threshold})")
        
        num_points = len(source_points)
        if num_points <= max_points:
            # If we have fewer points than max, just use all of them
            print(f"Using all {num_points} points (<= max_points)")
            return fit_rbf_model(source_points, target_points, epsilon, smoothing)
            
        # --- Greedy Selection Algorithm ---
        # 1. Start with a small random subset or just the point with max deformation
        # For stability, let's pick a few random points + max deformation point
        
        active_indices = []
        remaining_indices = list(range(num_points))
        
        # Calculate magnitudes to find max deformation
        displacements = target_points - source_points
        mags = np.linalg.norm(displacements, axis=1)
        max_def_idx = np.argmax(mags)
        
        active_indices.append(max_def_idx)
        remaining_indices.remove(max_def_idx)
        
        # Add a few random points to stabilize initial fit (e.g., 10 points)
        np.random.seed(42)
        initial_count = min(10, len(remaining_indices))
        if initial_count > 0:
            random_picks = np.random.choice(remaining_indices, initial_count, replace=False)
            for idx in random_picks:
                active_indices.append(idx)
                remaining_indices.remove(idx)
        
        current_rbf = None
        
        # Iterative Loop
        iteration = 0
        while len(active_indices) < max_points:
            iteration += 1
            
            # Fit RBF to active set
            active_source = source_points[active_indices]
            active_target = target_points[active_indices]
            
            current_rbf = fit_rbf_model(active_source, active_target, epsilon, smoothing)
            
            # Evaluate on remaining points
            if not remaining_indices:
                break
                
            # We need to evaluate RBF. RBFCore doesn't have a public 'predict' method exposed easily 
            # but we can reconstruct the evaluation logic.
            # Or better, add a predict method to RBFCore? 
            # For now, let's implement evaluation here to avoid changing RBFCore if possible, 
            # but changing RBFCore is cleaner.
            
            # Let's assume we add a predict method to RBFCore or do it manually here.
            # Manual evaluation:
            # s(x) = sum(w_i * phi(|x - c_i|)) + P(x)
            
            rem_source = source_points[remaining_indices]
            rem_target = target_points[remaining_indices]
            
            # Distance matrix: Rem vs Active
            # d[i, j] = dist(rem[i], active[j])
            d1 = rem_source[:, np.newaxis, :]
            d2 = active_source[np.newaxis, :, :]
            dists = np.sqrt(np.sum((d1 - d2)**2, axis=2))
            
            phi = np.sqrt(dists**2 + epsilon**2)
            
            # Polynomial
            # P = [1, x, y, z]
            P = np.ones((len(rem_source), 4))
            P[:, 1:] = rem_source
            
            # Prediction
            # weights: (num_active, 3)
            # poly_weights: (4, 3)
            pred_disp = phi @ current_rbf.weights + P @ current_rbf.polynomial_weights
            
            # Calculate Error
            # true_disp = rem_target - rem_source
            # error = || pred_disp - true_disp ||
            true_disp = rem_target - rem_source
            errors = np.linalg.norm(pred_disp - true_disp, axis=1)
            
            max_error_idx_local = np.argmax(errors)
            max_error = errors[max_error_idx_local]
            
            if max_error < error_threshold:
                print(f"Converged at iteration {iteration}. Max Error: {max_error:.6f}")
                break
                
            # Add point with max error
            best_idx = remaining_indices[max_error_idx_local]
            active_indices.append(best_idx)
            remaining_indices.pop(max_error_idx_local) # pop by index in list
            
            if iteration % 10 == 0:
                print(f"Iter {iteration}: Points {len(active_indices)}, Max Error {max_error:.6f}")
        
        print(f"Adaptive Fit Complete. Used {len(active_indices)} points.")
        return current_rbf

    def invoke(self, context, event):
        if not self.filepath:
            blend_filepath = context.blend_data.filepath
            if blend_filepath:
                self.filepath = os.path.splitext(blend_filepath)[0] + "_rbf.json"
            else:
                self.filepath = "rbf_data.json"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        obj = context.active_object
        props = context.scene.openfitter_rbf_props
        
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Active object must be a Mesh")
            return {'CANCELLED'}
            
        if not obj.data.shape_keys:
            self.report({'ERROR'}, "Object has no shape keys")
            return {'CANCELLED'}
            
        basis_name = props.basis_shape_key
        target_name = props.target_shape_key
        
        if basis_name not in obj.data.shape_keys.key_blocks:
            self.report({'ERROR'}, f"Basis Shape Key '{basis_name}' not found")
            return {'CANCELLED'}
            
        if target_name not in obj.data.shape_keys.key_blocks:
            self.report({'ERROR'}, f"Target Shape Key '{target_name}' not found")
            return {'CANCELLED'}
            
        # --- 1. Main Deformation (Basis -> Target) ---
        print(f"Extracting vertices from {obj.name}...")
        
        basis_block = obj.data.shape_keys.key_blocks[basis_name]
        target_block = obj.data.shape_keys.key_blocks[target_name]
        
        basis_verts = extract_vertices(basis_block)
        target_verts = extract_vertices(target_block)
        
        deltas = target_verts - basis_verts
        
        # Filter
        centers, deltas_filtered, _ = filter_significant_points(basis_verts, deltas)
        print(f"Points with delta > 0.0001: {len(centers)} / {len(basis_verts)}")
        
        if len(centers) == 0:
            self.report({'WARNING'}, "No significant deformation found between keys.")
            return {'CANCELLED'}

        # Mirror
        if props.enable_x_mirror:
            print("Applying X-Mirroring...")
            centers, deltas_filtered = apply_x_mirror(centers, deltas_filtered)
            print(f"Points after mirroring: {len(centers)}")

        # Downsample (Legacy Grid Sampling - Removed in favor of Adaptive Greedy)
        # centers, deltas_filtered = downsample_points(centers, deltas_filtered, props.epsilon, props.max_points)
        # print(f"Points after Grid Filter: {len(centers)}")

        # Fit RBF
        print("Fitting Main RBF...")
        target_points = centers + deltas_filtered
        
        start_time = time.time()
        # Pass max_points from props
        rbf = self.create_adaptive_deformation_field(centers, target_points, props.epsilon, props.smoothing, max_points=props.max_points)
        print(f"RBF Fit finished in {time.time() - start_time:.4f}s")
        
        # Init Export Data
        export_data = {
            "epsilon": float(rbf.epsilon),
            "centers": centers.tolist(),
            "weights": rbf.weights.tolist(),
            "poly_weights": rbf.polynomial_weights.tolist(),
            "shape_keys": []
        }

        # --- 2. Additional Shape Keys ---
        target_body = props.target_body_object
        
        if target_body and target_body.type == 'MESH' and target_body.data.shape_keys:
            self.process_target_body_keys(target_body, props, export_data)
        else:
            self.process_fallback_keys(obj, basis_name, target_name, target_verts, props, export_data)
        
        with open(self.filepath, 'w') as f:
            json.dump(export_data, f)
            
        self.report({'INFO'}, f"Saved RBF data to {self.filepath} (with {len(export_data['shape_keys'])} extra shapes)")
        return {'FINISHED'}

    def process_target_body_keys(self, target_body, props, export_data):
        print(f"Processing shape keys from Target Body: {target_body.name}")
        
        tb_mesh = target_body.data
        tb_basis_key = tb_mesh.shape_keys.key_blocks[0]
        tb_basis_verts = extract_vertices(tb_basis_key)
        
        for key_block in tb_mesh.shape_keys.key_blocks:
            if key_block == tb_basis_key: continue
            
            print(f"Processing Target Body Key: {key_block.name}")
            
            tb_key_verts = extract_vertices(key_block)
            key_deltas = tb_key_verts - tb_basis_verts
            
            # Identify Active and Anchor points
            active_centers, active_deltas, key_mask = filter_significant_points(tb_basis_verts, key_deltas)
            
            if len(active_centers) == 0:
                continue
            
            # Anchor Points (Static)
            anchor_mask = ~key_mask
            anchor_centers = tb_basis_verts[anchor_mask]
            anchor_deltas = key_deltas[anchor_mask] # Should be (0,0,0)
            
            # Combine
            key_centers = np.vstack([active_centers, anchor_centers])
            key_deltas_filtered = np.vstack([active_deltas, anchor_deltas])

            # Mirror
            if props.enable_x_mirror:
                key_centers, key_deltas_filtered = apply_x_mirror(key_centers, key_deltas_filtered)

            # Downsample (Legacy - Removed)
            # key_centers, key_deltas_filtered = downsample_points(key_centers, key_deltas_filtered, props.epsilon, props.max_points)
            
            # --- Two-Step Calculation ---
            print(f"Fitting RBF for {key_block.name} (2-Step Calculation)...")
            
            # Step 1: Basis -> 0.5
            step1_centers = key_centers
            step1_deltas = key_deltas_filtered * 0.5
            step1_targets = step1_centers + step1_deltas
            
            rbf_step1 = self.create_adaptive_deformation_field(step1_centers, step1_targets, props.epsilon, props.smoothing, max_points=props.max_points)
            
            # Step 2: 0.5 -> 1.0
            key_target_points = key_centers + key_deltas_filtered # Target at 1.0
            step2_centers = step1_targets
            step2_targets = key_target_points
            
            rbf_step2 = self.create_adaptive_deformation_field(step2_centers, step2_targets, props.epsilon, props.smoothing, max_points=props.max_points)
            
            # Calculate Bounds (Active Points + Mirror if needed)
            # We use the original active_centers for bounds calculation
            min_b, max_b = calculate_bounds(active_centers, props.mask_margin, props.enable_x_mirror)
            
            # Export Entries
            export_data["shape_keys"].append(create_rbf_entry(
                key_block.name, 50.0, rbf_step1, step1_centers, min_b, max_b
            ))
            
            export_data["shape_keys"].append(create_rbf_entry(
                key_block.name, 100.0, rbf_step2, step2_centers, min_b, max_b
            ))

    def process_fallback_keys(self, obj, basis_name, target_name, target_verts, props, export_data):
        # Fallback: Use extra keys on the active object
        for key_block in obj.data.shape_keys.key_blocks:
            if key_block.name == basis_name or key_block.name == target_name:
                continue
                
            print(f"Processing additional shape key (Active Object): {key_block.name}")
            
            key_verts = extract_vertices(key_block)
            key_deltas = key_verts - target_verts
            
            # Filter
            key_centers, key_deltas_filtered, _ = filter_significant_points(target_verts, key_deltas)
            
            if len(key_centers) == 0:
                print(f"Skipping {key_block.name}: No significant difference from Target.")
                continue
                
            # Mirror
            if props.enable_x_mirror:
                key_centers, key_deltas_filtered = apply_x_mirror(key_centers, key_deltas_filtered)

            # Downsample (Legacy - Removed)
            # key_centers, key_deltas_filtered = downsample_points(key_centers, key_deltas_filtered, props.epsilon, props.max_points)
            
            # Fit RBF
            print(f"Fitting RBF for {key_block.name} ({len(key_centers)} points)...")
            key_target_points = key_centers + key_deltas_filtered
            
            key_rbf = self.create_adaptive_deformation_field(key_centers, key_target_points, props.epsilon, props.smoothing, max_points=props.max_points)
            
            # Calculate Bounds
            # For fallback, active points are key_centers (since we filtered by delta)
            # But key_centers might include mirrored points now.
            # calculate_bounds handles mirroring if we pass the raw points, but here key_centers is already mirrored.
            # So we just pass key_centers and disable internal mirroring in calculate_bounds.
            min_b, max_b = calculate_bounds(key_centers, props.mask_margin, enable_mirror=False)
            
            export_data["shape_keys"].append(create_rbf_entry(
                key_block.name, 100.0, key_rbf, key_centers, min_b, max_b
            ))

# ------------------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------------------

def extract_vertices(key_block):
    num_verts = len(key_block.data)
    verts = np.zeros((num_verts, 3), dtype=np.float32)
    key_block.data.foreach_get("co", verts.ravel())
    return verts

def filter_significant_points(centers, deltas, threshold=0.0001):
    mags = np.linalg.norm(deltas, axis=1)
    mask = mags > threshold
    return centers[mask], deltas[mask], mask

def apply_x_mirror(centers, deltas):
    # Mirror points with X > epsilon (positive side)
    mirror_mask = centers[:, 0] > 0.0001
    mirror_centers = centers[mirror_mask].copy()
    mirror_deltas = deltas[mirror_mask].copy()
    
    mirror_centers[:, 0] *= -1
    mirror_deltas[:, 0] *= -1
    
    return np.vstack([centers, mirror_centers]), np.vstack([deltas, mirror_deltas])

def downsample_points(centers, deltas, epsilon, max_points):
    # Grid Sampling
    grid_spacing = max(epsilon * 0.2, 0.001)
    grid = {}
    for i, p in enumerate(centers):
        key = (int(p[0]/grid_spacing), int(p[1]/grid_spacing), int(p[2]/grid_spacing))
        if key not in grid:
            grid[key] = i
    
    indices = list(grid.values())
    indices.sort()
    centers = centers[indices]
    deltas = deltas[indices]
    
    # Random Downsampling
    if len(centers) > max_points:
        np.random.seed(42)
        indices = np.random.choice(len(centers), max_points, replace=False)
        centers = centers[indices]
        deltas = deltas[indices]
        
    return centers, deltas

def calculate_bounds(points, margin, enable_mirror=False):
    # Calculate bounds of the active points
    # If mirror is enabled, we should include the mirrored bounds too
    
    min_b = np.min(points, axis=0)
    max_b = np.max(points, axis=0)
    
    if enable_mirror:
        # If we mirror, the X bounds will be symmetric
        # Max X becomes max(Max X, -Min X)
        # Min X becomes min(Min X, -Max X)
        # But simpler: just mirror the points and check min/max
        mirror_points = points.copy()
        mirror_points[:, 0] *= -1
        
        all_points = np.vstack([points, mirror_points])
        min_b = np.min(all_points, axis=0)
        max_b = np.max(all_points, axis=0)
