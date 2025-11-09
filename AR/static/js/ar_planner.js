import * as THREE from 'https://unpkg.com/three@0.160.0/build/three.module.js?module';
import { ARButton } from 'https://unpkg.com/three@0.160.0/examples/jsm/webxr/ARButton.js?module';
import { GLTFLoader } from 'https://unpkg.com/three@0.160.0/examples/jsm/loaders/GLTFLoader.js?module';

(function(){
  const wrap = document.getElementById('arCanvasWrap');
  const startBtn = document.getElementById('arStartBtn');
  const snapBtn = document.getElementById('arSnapshotBtn');
  const swapBtn = document.getElementById('arSwapBtn');
  const list = document.getElementById('plantList');
  const ov = {
    el: document.getElementById('plantOverlay'),
    name: document.getElementById('ovName'),
    sun: document.getElementById('ovSunlight'),
    spacing: document.getElementById('ovSpacing'),
    water: document.getElementById('ovWatering'),
  };
  const bannerTop = document.getElementById('selectedBannerTop');
  const aiPanel = document.getElementById('aiPanel');
  async function fetchAITipsFor(plant){
    try{
      if (!plant || !plant.name || !aiPanel) return;
      aiPanel.textContent = 'AI tips loading...';
      const msg = `In AR, give short bullet tips to place and care for ${plant.name}. Keep it 4-6 bullets, concise.`;
      const res = await fetch('/api/ai/chat', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({message: msg})});
      const data = await res.json();
      aiPanel.textContent = (data && data.assistant) ? data.assistant : '';
    }catch(e){ aiPanel.textContent = ''; }
  }

  let renderer, scene, camera;
  let controller;
  let hitTestSource = null;
  let hitTestSourceRequested = false;
  let reticle;
  let selectedPlant = null;
  let placeOnReticle = false;
  let activeButton = null;
  const loader = new GLTFLoader();
  const placed = []; // placed objects

  // Fallback camera preview support
  let mediaStream = null;
  let videoEl = null;
  let useFrontCamera = false;
  let fallbackMode = false;

  function init(){
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(wrap.clientWidth, wrap.clientHeight);
    renderer.xr.enabled = true;
    wrap.innerHTML='';
    wrap.appendChild(renderer.domElement);

    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(70, wrap.clientWidth / wrap.clientHeight, 0.01, 20);

    const light = new THREE.HemisphereLight(0xffffff, 0xbbbbbb, 1.0);
    scene.add(light);

    reticle = new THREE.Mesh(
      new THREE.RingGeometry(0.12, 0.15, 32).rotateX(-Math.PI/2),
      new THREE.MeshBasicMaterial({ color: 0x00aaff })
    );
    reticle.matrixAutoUpdate = false;
    reticle.visible = false;
    scene.add(reticle);

    controller = renderer.xr.getController(0);
    controller.addEventListener('select', onSelect);
    scene.add(controller);

    window.addEventListener('resize', onWindowResize);
  }

  function onWindowResize(){
    if (!renderer) return;
    const w = wrap.clientWidth, h = wrap.clientHeight;
    renderer.setSize(w, h);
    camera.aspect = w/h; camera.updateProjectionMatrix();
  }

  async function startAR(){
    let xrSupported = false;
    try {
      if (navigator.xr && navigator.xr.isSessionSupported){
        xrSupported = await navigator.xr.isSessionSupported('immersive-ar');
      }
    } catch (_err) {
      xrSupported = false;
    }

    try{
      if (xrSupported && ARButton){
        if (!renderer) init();
        const arBtn = ARButton.createButton(renderer, { requiredFeatures: ['hit-test'] });
        arBtn.style.display='none';
        document.body.appendChild(arBtn);
        renderer.domElement.addEventListener('touchstart', onTouchStart, { passive:false });
        renderer.domElement.addEventListener('touchmove', onTouchMove, { passive:false });
        renderer.domElement.addEventListener('touchend', onTouchEnd, { passive:false });
        renderer.domElement.addEventListener('click', (e)=>{ pickObject(e.clientX, e.clientY); });
        renderer.setAnimationLoop(render);
        arBtn.click();
        fallbackMode = false;
        return;
      }
    }catch(_e){}
    await startCameraPreview();
  }

  async function startCameraPreview(){
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia){
      alert('Camera preview is not supported in this browser.');
      return;
    }
    try{
      stopCameraPreview();
      const constraints = { video: { facingMode: useFrontCamera ? 'user' : 'environment' }, audio: false };
      mediaStream = await navigator.mediaDevices.getUserMedia(constraints);
      if (!videoEl){
        videoEl = document.createElement('video');
        videoEl.setAttribute('playsinline','true');
        videoEl.autoplay = true;
        videoEl.muted = true;
        videoEl.style.width = '100%';
        videoEl.style.height = '100%';
        videoEl.style.objectFit = 'cover';
      }
      videoEl.srcObject = mediaStream;
      wrap.innerHTML='';
      wrap.appendChild(videoEl);
      fallbackMode = true;
    }catch(e){
      alert('Camera permission is required to start AR preview.');
      console.error('Camera preview error', e);
    }
  }

  function stopCameraPreview(){
    if (mediaStream){
      mediaStream.getTracks().forEach(t=>t.stop());
      mediaStream = null;
    }
  }

  function onSelect(){
    if (reticle.visible){
      if (selectedPlant){
        addPlantAt(reticle.matrix, selectedPlant);
      } else if (activeObj){
        activeObj.position.setFromMatrixPosition(reticle.matrix);
      }
    }
  }

  function addPlantAt(matrix, plant){
    const { model, scale } = plant;
    if (!model){ return; }
    const obj = model.scene ? model.scene.clone(true) : model.clone(true);
    obj.position.setFromMatrixPosition(matrix);
    obj.quaternion.setFromRotationMatrix(matrix);
    const s = scale || 1;
    obj.scale.setScalar(s);
    obj.userData.plant = plant;
    scene.add(obj);
    placed.push(obj);
    setOverlay(plant);
  }

  function metersFromCm(cm){ return (Number(cm)||0)/100; }
  function computeScale(plant){
    // scale to approximate width to growth_width_cm if available
    const w = metersFromCm(plant.growth_width_cm);
    const h = metersFromCm(plant.growth_height_cm);
    // default nominal gltf size ~1 meter; scale down appropriately
    if (w>0){ return Math.max(0.1, Math.min(2.5, w)); }
    if (h>0){ return Math.max(0.1, Math.min(2.5, h)); }
    return 0.5;
  }

  async function loadSelected(button){
    const name = button.dataset.name;
    const rawModelUrl = (button.dataset.model || '').trim();
    const modelUrl = rawModelUrl && rawModelUrl.toLowerCase() !== 'none' ? rawModelUrl : '';
    const gh = parseInt(button.dataset.height||'')||null;
    const gw = parseInt(button.dataset.width||'')||null;
    const sunlight = button.dataset.sunlight || '';
    const spacing = button.dataset.spacing || '';
    const watering = button.dataset.watering || '';

    // build base plant, set selection and overlay immediately
    const basePlant = {
      name,
      model: null,
      growth_height_cm: gh,
      growth_width_cm: gw,
      sunlight, spacing_cm: spacing, watering_needs: watering,
      scale: computeScale({growth_height_cm: gh, growth_width_cm: gw})
    };
    selectedPlant = basePlant;
    setOverlay(selectedPlant);
    fetchAITipsFor(selectedPlant);

    // highlight selected button
    if (activeButton){
      activeButton.classList.remove('is-selected');
      activeButton.removeAttribute('aria-current');
      activeButton.removeAttribute('aria-selected');
    }
    button.classList.add('is-selected');
    button.setAttribute('aria-current','true');
    button.setAttribute('aria-selected','true');
    activeButton = button;

    if (!modelUrl){
      alert('This plant has no 3D model set. Ask admin to add a GLB model URL.');
      return;
    }

    try{
      const gltf = await loader.loadAsync(modelUrl);
      selectedPlant = { ...basePlant, model: gltf };
      setOverlay(selectedPlant);
    fetchAITipsFor(selectedPlant);

      // if AR session is active, place immediately on reticle when available
      if (renderer && renderer.xr && renderer.xr.isPresenting){
        if (reticle && reticle.visible){
          addPlantAt(reticle.matrix, selectedPlant);
        } else {
          placeOnReticle = true;
        }
      }
    }catch(e){
      console.error('GLTF load failed', e);
      alert('Could not load 3D model.');
    }
  }

  function setOverlay(plant){
    if (!plant) return;
    ov.name.textContent = plant.name || '';
    ov.sun.textContent = plant.sunlight ? ('Sunlight: ' + plant.sunlight) : '';
    ov.spacing.textContent = plant.spacing_cm ? ('Spacing: ' + plant.spacing_cm + ' cm') : '';
    ov.water.textContent = plant.watering_needs ? ('Watering: ' + plant.watering_needs) : '';
    if (bannerTop) { bannerTop.textContent = plant.name || ''; }
  }

  let activeObj=null, lastTouches=null, lastAngle=0, lastDist=0;

  function screenToNDC(x,y){
    const rect = renderer.domElement.getBoundingClientRect();
    return { x: ( (x-rect.left)/rect.width )*2 - 1, y: - ( (y-rect.top)/rect.height )*2 + 1 };
  }
  function pickObject(clientX, clientY){
    const ndc = screenToNDC(clientX, clientY);
    const raycaster = new THREE.Raycaster();
    raycaster.setFromCamera(new THREE.Vector2(ndc.x, ndc.y), camera);
    const hits = raycaster.intersectObjects(placed, true);
    if (hits.length){
      let obj = hits[0].object;
      while(obj && !placed.includes(obj)) obj = obj.parent;
      activeObj = obj || activeObj;
    }
  }

  function onTouchMove(e){
    if (!renderer || !renderer.xr.isPresenting) return;
    if (!activeObj && placed.length) activeObj = placed[placed.length-1];
    if (!activeObj) return;

    if (e.touches.length===1){
      e.preventDefault();
      const t = e.touches[0];
      // move: project reticle to touch point by offsetting reticle to camera-facing plane approx
      // approximate by placing at reticle height but towards camera ray
      const ndc = screenToNDC(t.clientX, t.clientY);
      const raycaster = new THREE.Raycaster();
      raycaster.setFromCamera(new THREE.Vector2(ndc.x, ndc.y), camera);
      const plane = new THREE.Plane(new THREE.Vector3(0,1,0), 0);
      const intersection = new THREE.Vector3();
      raycaster.ray.intersectPlane(plane, intersection);
      if (intersection){ activeObj.position.lerp(intersection, 0.4); }
    } else if (e.touches.length===2){
      e.preventDefault();
      const [a,b] = [e.touches[0], e.touches[1]];
      const dx = b.clientX - a.clientX, dy = b.clientY - a.clientY;
      const dist = Math.hypot(dx, dy);
      const angle = Math.atan2(dy, dx);
      if (lastDist){
        const scale = THREE.MathUtils.clamp(dist/lastDist, 0.8, 1.25);
        activeObj.scale.multiplyScalar(scale);
      }
      if (lastAngle){
        const da = angle - lastAngle;
        activeObj.rotation.y += da;
      }
      lastDist = dist; lastAngle = angle;
    }
  }
  function onTouchStart(e){
    if (e.touches.length===1){ pickObject(e.touches[0].clientX, e.touches[0].clientY); }
    if (e.touches.length<2){ lastDist=0; lastAngle=0; }
  }
  function onTouchEnd(){ lastDist=0; lastAngle=0; }

  function render(timestamp, frame){
    const session = renderer.xr.getSession();
    if (frame){
      const refSpace = renderer.xr.getReferenceSpace();
      if (!hitTestSourceRequested){
        session.requestReferenceSpace('viewer').then((rs)=>{
          session.requestHitTestSource({ space: rs }).then((source)=>{ hitTestSource = source; });
        });
        session.addEventListener('end', ()=>{ hitTestSourceRequested=false; hitTestSource=null; });
        hitTestSourceRequested = true;
      }
      if (hitTestSource){
        const hitTestResults = frame.getHitTestResults(hitTestSource);
        if (hitTestResults.length){
          const hit = hitTestResults[0];
          const pose = hit.getPose(renderer.xr.getReferenceSpace());
          reticle.visible = true;
          reticle.matrix.fromArray(pose.transform.matrix);
          if (placeOnReticle && selectedPlant){
            addPlantAt(reticle.matrix, selectedPlant);
            placeOnReticle = false;
          }
        } else {
          reticle.visible = false;
        }
      }
    }
    renderer.render(scene, camera);
  }

  function snapshot(){
    try{
      if (fallbackMode && videoEl){
        const canvas = document.createElement('canvas');
        canvas.width = videoEl.videoWidth || wrap.clientWidth;
        canvas.height = videoEl.videoHeight || wrap.clientHeight;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(videoEl, 0, 0, canvas.width, canvas.height);
        const url = canvas.toDataURL('image/png');
        const a = document.createElement('a'); a.href = url; a.download = 'ar-garden.png'; a.click();
        return;
      }
      const url = renderer.domElement.toDataURL('image/png');
      const a = document.createElement('a');
      a.href = url; a.download = 'ar-garden.png'; a.click();
    }catch(e){
      alert('Snapshot not supported on this device.');
    }
  }

  // Bind UI
  if (list){
    const onListActivate = (e)=>{
      const btn = e.target.closest('.plant-item');
      if (!btn) return;
      e.preventDefault();
      loadSelected(btn);
    };
    list.addEventListener('click', onListActivate);
    list.addEventListener('keydown', (e)=>{
      const btn = e.target.closest('.plant-item');
      if (!btn) return;
      if (e.key === 'Enter' || e.key === ' '){ e.preventDefault(); onListActivate(e); }
    });
    // direct handlers on each button to ensure activation even if delegation fails
    const btns = list.querySelectorAll('.plant-item');
    btns.forEach((btn)=>{
      btn.addEventListener('click', (e)=>{ e.preventDefault(); loadSelected(btn); });
      btn.addEventListener('keydown', (e)=>{ if (e.key==='Enter' || e.key===' '){ e.preventDefault(); loadSelected(btn); }});
      btn.addEventListener('touchend', (e)=>{ e.preventDefault(); loadSelected(btn); });
    });
  }
  // Global fallback (in case list binding misses dynamically rendered buttons)
  document.addEventListener('click', (e)=>{
    const btn = e.target.closest && e.target.closest('.plant-item');
    if (!btn) return;
    e.preventDefault();
    loadSelected(btn);
  }, true);

  if (startBtn){ startBtn.addEventListener('click', startAR); }
  if (swapBtn){ swapBtn.addEventListener('click', async ()=>{ useFrontCamera = !useFrontCamera; if (fallbackMode){ await startCameraPreview(); } }); }
  if (snapBtn){ snapBtn.addEventListener('click', snapshot); }
})();
