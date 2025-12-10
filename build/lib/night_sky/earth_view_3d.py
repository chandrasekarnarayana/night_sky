"""
3D textured Earth globe using pyqtgraph.opengl with click-to-select location.

Renders a sphere with a simple procedural texture (land in green/brown, ocean in blue).
Clicking on the globe converts the click ray to a sphere intersection, then converts
the intersection point to lat/lon.

This module is only imported if OpenGL is available.
"""

from PyQt5.QtCore import Qt, pyqtSignal
import numpy as np

# Conditional import for OpenGL support
try:
    from pyqtgraph.opengl import GLViewWidget, GLMeshItem
    import pyqtgraph.opengl as gl
    OPENGL_AVAILABLE = True
except ImportError:
    OPENGL_AVAILABLE = False


class EarthView3D:
    """
    3D textured Earth sphere with click-to-select location support.
    
    Only available if OpenGL is available. Emits location_changed signal
    when user clicks on the globe.
    
    Emits:
        location_changed: (lat_deg, lon_deg) when user clicks on globe
    """
    
    # Class-level signal (defined if OpenGL available)
    if OPENGL_AVAILABLE:
        location_changed = pyqtSignal(float, float)
        
        def __init__(self):
            """Initialize 3D Earth globe."""
            self.view = GLViewWidget()
            self.view.setWindowTitle("Earth View (3D)")
            self.view.setCameraPosition(distance=2.5, elevation=30, azimuth=45)
            
            # Create grid for reference
            grid = gl.GLGridItem()
            grid.scale(2, 2, 1)
            self.view.addItem(grid)
            
            # Create Earth sphere
            self._create_earth_sphere()
            
            # Connect mouse click event
            self.view.scene().sigMouseClicked.connect(self._on_mouse_clicked)
        
        def _create_earth_sphere(self, radius=1.0, subdivisions=32):
            """
            Create a sphere mesh with a simple procedural texture.
            
            Args:
                radius: Sphere radius
                subdivisions: Number of subdivisions for smoothness
            """
            # Generate sphere vertices and faces using icosphere subdivision
            verts, faces = self._generate_uv_sphere(radius, subdivisions)
            
            # Create simple texture (procedural)
            colors = self._generate_earth_colors(verts)
            
            # Create mesh item
            mesh_data = gl.MeshData(vertexes=verts, faces=faces, vertexColors=colors)
            self.sphere = GLMeshItem(meshData=mesh_data, smooth=True, drawEdges=False)
            self.view.addItem(self.sphere)
        
        def _generate_uv_sphere(self, radius=1.0, subdivisions=32):
            """
            Generate vertices and faces for a UV sphere.
            
            Args:
                radius: Sphere radius
                subdivisions: Number of meridian/parallel divisions
            
            Returns:
                (vertices, faces): NumPy arrays of shape (N, 3) and (M, 3)
            """
            verts = []
            faces = []
            
            # Generate vertices (lat/lon grid)
            for lat_i in range(subdivisions + 1):
                lat_rad = np.pi * (lat_i / subdivisions - 0.5)  # -π/2 to π/2
                for lon_i in range(subdivisions + 1):
                    lon_rad = 2 * np.pi * (lon_i / subdivisions)  # 0 to 2π
                    
                    x = radius * np.cos(lat_rad) * np.cos(lon_rad)
                    y = radius * np.cos(lat_rad) * np.sin(lon_rad)
                    z = radius * np.sin(lat_rad)
                    verts.append([x, y, z])
            
            verts = np.array(verts, dtype=np.float32)
            
            # Generate faces (triangles)
            for lat_i in range(subdivisions):
                for lon_i in range(subdivisions):
                    v0 = lat_i * (subdivisions + 1) + lon_i
                    v1 = v0 + 1
                    v2 = v0 + (subdivisions + 1)
                    v3 = v2 + 1
                    
                    faces.append([v0, v2, v1])
                    faces.append([v1, v2, v3])
            
            faces = np.array(faces, dtype=np.uint32)
            return verts, faces
        
        def _generate_earth_colors(self, verts):
            """
            Generate simple procedural Earth colors based on vertex positions.
            
            Land (green/brown) if noise > 0.3, else ocean (blue).
            
            Args:
                verts: Vertex array of shape (N, 3)
            
            Returns:
                colors: RGBA colors array of shape (N, 4)
            """
            colors = np.zeros((len(verts), 4), dtype=np.uint8)
            
            for i, v in enumerate(verts):
                # Simple Perlin-like noise approximation using sine waves
                x, y, z = v
                # Use multiple sine waves to create landmass-like patterns
                noise = (
                    0.4 * np.sin(x * 3) * np.cos(y * 2) +
                    0.3 * np.sin(y * 4) * np.cos(z * 3) +
                    0.3 * np.sin(z * 2) * np.cos(x * 4)
                )
                
                if noise > 0.3:
                    # Land: green/brown gradient
                    colors[i] = [100 + int(50 * noise), 150, 50, 255]
                else:
                    # Ocean: blue
                    colors[i] = [0, 100, 200, 255]
            
            return colors
        
        def _on_mouse_clicked(self, event):
            """Handle mouse clicks on the globe; convert to lat/lon via ray casting."""
            if event.button() != Qt.LeftButton:
                return
            
            # Get click position in viewport
            pos = event.scenePos()
            
            # Cast ray from camera through click position to sphere
            # (Simplified: assume orthogonal projection and find intersection)
            # For full accuracy, would use gluUnproject with depth testing
            try:
                lat, lon = self._ray_sphere_intersection(pos)
                if lat is not None:
                    self.location_changed.emit(lat, lon)
            except Exception:
                pass  # Silently ignore ray casting failures
        
        def _ray_sphere_intersection(self, screen_pos):
            """
            Convert screen click position to lat/lon via ray-sphere intersection.
            
            Simplified approach: use camera position and view matrix to compute
            ray direction, then intersect with unit sphere.
            
            Args:
                screen_pos: QPointF in scene coordinates
            
            Returns:
                (lat_deg, lon_deg) or (None, None) if no intersection
            """
            # Get camera info
            camera = self.view.cameraParams()
            
            # Normalize screen position to [-1, 1]
            rect = self.view.rect()
            norm_x = (screen_pos.x() - rect.left()) / rect.width() * 2 - 1
            norm_y = (screen_pos.y() - rect.top()) / rect.height() * 2 - 1
            
            # Simple ray casting: assume ray from (norm_x, norm_y, -2) towards (norm_x, norm_y, 1)
            # and intersect with unit sphere at origin
            ray_origin = np.array([norm_x * 2.5, norm_y * 2.5, -2.0])
            ray_dir = np.array([0, 0, 1])
            ray_dir = ray_dir / np.linalg.norm(ray_dir)
            
            # Ray-sphere intersection: |ray_origin + t * ray_dir|^2 = 1
            # Solving: t = -b ± sqrt(b^2 - c), where a=1, b=ray_origin·ray_dir, c=|ray_origin|^2 - 1
            a = np.dot(ray_dir, ray_dir)
            b = 2 * np.dot(ray_origin, ray_dir)
            c = np.dot(ray_origin, ray_origin) - 1.0
            
            discriminant = b * b - 4 * a * c
            if discriminant < 0:
                return None, None
            
            t1 = (-b - np.sqrt(discriminant)) / (2 * a)
            t2 = (-b + np.sqrt(discriminant)) / (2 * a)
            t = t1 if t1 > 0 else t2
            
            if t < 0:
                return None, None
            
            # Intersection point
            intersection = ray_origin + t * ray_dir
            
            # Convert 3D Cartesian to lat/lon
            lat_rad = np.arcsin(intersection[2])
            lon_rad = np.arctan2(intersection[1], intersection[0])
            
            lat_deg = np.degrees(lat_rad)
            lon_deg = np.degrees(lon_rad)
            if lon_deg < 0:
                lon_deg += 360
            
            return lat_deg, lon_deg
        
        def set_marker(self, lat_deg, lon_deg):
            """
            Highlight a location on the globe with a marker.
            
            Args:
                lat_deg: Latitude in degrees
                lon_deg: Longitude in degrees
            """
            # TODO: Add a small sphere or marker at (lat_deg, lon_deg)
            pass
        
        def export_png(self, path, width=1600, height=900):
            """
            Export the globe view to PNG.
            
            Args:
                path: File path to save PNG
                width: Width in pixels
                height: Height in pixels
            """
            original_size = self.view.size()
            self.view.resize(width, height)
            pixmap = self.view.grabFramebuffer()
            pixmap.save(str(path))
            self.view.resize(original_size)
    
    else:
        # If OpenGL not available, define a stub class
        def __init__(self):
            raise RuntimeError("OpenGL not available; EarthView3D requires GPU support")
