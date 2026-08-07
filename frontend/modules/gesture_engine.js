/**
 * Gesture Recognition & 3D Interaction Engine for FALSO Spatial OS.
 * Translates MediaPipe landmarks into 3D gestures (Pinch, Grab, Point, ThumbsUp).
 */

import * as THREE from 'three';

export class GestureEngine {
  constructor(scene, camera) {
    this.scene = scene;
    this.camera = camera;
    this.THREE = THREE;

    this.raycaster = new THREE.Raycaster();
    this.pointerMesh = this.createPointerMesh();
    this.scene.add(this.pointerMesh);

    this.grabbedEntity = null;
    this.gestureState = {
      isPointing: false,
      isPinching: false,
      isGrabbing: false,
      isThumbsUp: false,
      pointingRay: null
    };
  }

  createPointerMesh() {
    const THREE = this.THREE;
    const geom = new THREE.SphereGeometry(0.04, 16, 16);
    const mat = new THREE.MeshBasicMaterial({ color: 0x00FFFF, transparent: true, opacity: 0.8 });
    const mesh = new THREE.Mesh(geom, mat);
    mesh.visible = false;
    return mesh;
  }

  processLandmarks(handResults, spatialObjectManager) {
    if (!handResults || !handResults.landmarks || handResults.landmarks.length === 0) {
      this.pointerMesh.visible = false;
      this.releaseGrabbed();
      return null;
    }

    const landmarks = handResults.landmarks[0];
    const indexTip = landmarks[8];
    const thumbTip = landmarks[4];
    const wrist = landmarks[0];
    const middleMcp = landmarks[9];

    // 1. Screen to 3D Raycasting
    // Normalized Screen Coordinates: x [0..1], y [0..1] -> NDC [-1..1]
    const ndcX = (1 - indexTip.x) * 2 - 1; // Mirrored for natural feedback
    const ndcY = -(indexTip.y * 2 - 1);

    this.raycaster.setFromCamera({ x: ndcX, y: ndcY }, this.camera);

    // Update 3D Pointer Mesh position in space
    const targetDist = 3.5;
    const rayDir = this.raycaster.ray.direction.clone().multiplyScalar(targetDist);
    const pointerPos = this.camera.position.clone().add(rayDir);
    this.pointerMesh.position.copy(pointerPos);
    this.pointerMesh.visible = true;

    // 2. Gesture Calculations
    const pinchDist = Math.hypot(thumbTip.x - indexTip.x, thumbTip.y - indexTip.y, thumbTip.z - indexTip.z);
    const palmSize = Math.hypot(wrist.x - middleMcp.x, wrist.y - middleMcp.y, wrist.z - middleMcp.z);
    const isPinching = (pinchDist / (palmSize || 1)) < 0.35;

    // Grab Check (Fist)
    const fingerTips = [4, 8, 12, 16, 20];
    let totalDist = 0;
    for (const idx of fingerTips) {
      const tip = landmarks[idx];
      totalDist += Math.hypot(tip.x - wrist.x, tip.y - wrist.y, tip.z - wrist.z);
    }
    const isGrabbing = (totalDist / fingerTips.length) < 0.25;

    this.gestureState.isPinching = isPinching;
    this.gestureState.isGrabbing = isGrabbing;

    // 3. Object Hover & Grab Logic
    const intersects = this.raycaster.intersectObjects(spatialObjectManager.containerGroup.children, true);
    
    let hoveredEntity = null;
    if (intersects.length > 0) {
      let topObj = intersects[0].object;
      while (topObj.parent && topObj.parent !== spatialObjectManager.containerGroup) {
        topObj = topObj.parent;
      }
      for (const [id, entity] of spatialObjectManager.entities.entries()) {
        if (entity.group === topObj) {
          hoveredEntity = entity;
          break;
        }
      }
    }

    if (isPinching || isGrabbing) {
      if (!this.grabbedEntity && hoveredEntity) {
        this.grabbedEntity = hoveredEntity;
        console.log('[GestureEngine] Grabbed 3D object:', hoveredEntity.data.name);
      }
      if (this.grabbedEntity) {
        // Move grabbed object smoothly to pointer position
        this.grabbedEntity.group.position.lerp(pointerPos, 0.2);
        // Expose to window for Voice + Gesture context
        window.gestureContext = {
          selectedObjects: [this.grabbedEntity.data],
          gesture: isPinching ? 'pinch' : 'grab',
          timestamp: Date.now()
        };
      }
    } else {
      this.releaseGrabbed();
    }

    return {
      hoveredEntity,
      grabbedEntity: this.grabbedEntity,
      isPinching,
      isGrabbing
    };
  }

  releaseGrabbed() {
    if (this.grabbedEntity) {
      console.log('[GestureEngine] Released object:', this.grabbedEntity.data.name);
      this.grabbedEntity = null;
      window.gestureContext = null;
    }
  }
}
