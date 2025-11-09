import os
import json
from typing import Dict

from PIL import Image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, 'models')
LABELS_PATH = os.path.join(MODELS_DIR, 'labels.json')
MODEL_PATH = os.path.join(MODELS_DIR, 'latest.pt')

_model = None
_idx_to_class = None
_transform = None
_device = None


def _setup_torch():
    global _transform, _device
    try:
        import torch  # noqa: F401
        from torchvision import transforms  # noqa: F401
    except Exception:
        return False
    from torchvision import transforms as _tv_transforms
    import torch as _torch
    _device = _torch.device('cuda' if _torch.cuda.is_available() else 'cpu')
    _transform = _tv_transforms.Compose([
        _tv_transforms.Resize((224, 224)),
        _tv_transforms.ToTensor(),
        _tv_transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    return True


def _load_artifacts():
    global _model, _idx_to_class, _device
    try:
        import torch
        from torchvision import models
    except Exception:
        return {'error': 'Local ML runtime unavailable (torch/torchvision import failed).'}

    if not os.path.isfile(MODEL_PATH):
        return {'error': 'Model not trained yet'}

    class_to_idx: Dict[str, int] = {}
    if os.path.isfile(LABELS_PATH):
        try:
            with open(LABELS_PATH, 'r') as f:
                class_to_idx = json.load(f) or {}
        except Exception:
            class_to_idx = {}

    if _device is None or _transform is None:
        _setup_torch()
    _device = _device or (torch.device('cuda' if torch.cuda.is_available() else 'cpu'))

    ckpt = torch.load(MODEL_PATH, map_location=_device)
    if not class_to_idx and isinstance(ckpt, dict) and 'class_to_idx' in ckpt and isinstance(ckpt['class_to_idx'], dict):
        class_to_idx = ckpt['class_to_idx']

    if not class_to_idx:
        return {'error': 'Model labels not found'}

    idx_to_class = {v: k for k, v in class_to_idx.items()}

    model = models.resnet18()
    in_features = model.fc.in_features
    model.fc = torch.nn.Linear(in_features, len(idx_to_class))
    state = ckpt.get('model_state') if isinstance(ckpt, dict) else ckpt
    model.load_state_dict(state)
    model.eval()
    _model = model.to(_device)
    _idx_to_class = idx_to_class
    return True


def predict_image(image_path: str) -> Dict:
    if _model is None or _idx_to_class is None:
        ok = _load_artifacts()
        if ok is not True:
            return ok if isinstance(ok, dict) else {'error': 'Model not trained yet'}

    if _transform is None:
        if not _setup_torch():
            return {'error': 'Local ML runtime unavailable (torch/torchvision import failed).'}
        import torch as _torch  # ensure device set
        # _device already set in _setup_torch

    try:
        import torch
    except Exception:
        return {'error': 'Local ML runtime unavailable (torch/torchvision import failed).'}

    img = Image.open(image_path).convert('RGB')
    x = _transform(img).unsqueeze(0).to(_device)
    with torch.no_grad():
        logits = _model(x)
        probs = torch.softmax(logits, dim=1).cpu().numpy()[0]
        top_idx = int(probs.argmax())
        top_prob = float(probs[top_idx])
        label = _idx_to_class[top_idx]
    return {'label': label, 'confidence': top_prob}
