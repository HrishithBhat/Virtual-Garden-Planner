import os
import json
from typing import Dict, Tuple

import torch
from torch import nn, optim
from torch.utils.data import DataLoader
from torchvision import datasets, transforms, models

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(BASE_DIR, 'dataset')
MODELS_DIR = os.path.join(BASE_DIR, 'models')
LABELS_PATH = os.path.join(MODELS_DIR, 'labels.json')
MODEL_PATH = os.path.join(MODELS_DIR, 'latest.pt')


def ensure_dirs():
    os.makedirs(DATASET_DIR, exist_ok=True)
    os.makedirs(MODELS_DIR, exist_ok=True)


def get_dataloaders(img_size: int = 224, batch_size: int = 16) -> Tuple[DataLoader, DataLoader, Dict[str, int]]:
    ensure_dirs()
    if not os.path.isdir(DATASET_DIR):
        raise RuntimeError(f"Dataset directory not found: {DATASET_DIR}")

    transform_train = transforms.Compose([
        transforms.Resize((img_size, img_size)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(15),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    transform_val = transforms.Compose([
        transforms.Resize((img_size, img_size)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    full_ds = datasets.ImageFolder(DATASET_DIR, transform=transform_train)
    class_to_idx = full_ds.class_to_idx

    # simple split: 90% train, 10% val per class
    n_total = len(full_ds)
    n_val = max(1, int(0.1 * n_total))
    n_train = max(1, n_total - n_val)
    train_ds, val_ds = torch.utils.data.random_split(full_ds, [n_train, n_val])
    # override val transform
    val_ds.dataset.transform = transform_val

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0)
    return train_loader, val_loader, class_to_idx


def build_model(num_classes: int) -> nn.Module:
    try:
        model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)  # torchvision>=0.13
    except Exception:
        try:
            model = models.resnet18(pretrained=True)
        except Exception:
            model = models.resnet18(pretrained=False)
    in_features = model.fc.in_features
    model.fc = nn.Linear(in_features, num_classes)
    return model


def train(num_epochs: int = 3, lr: float = 1e-3, img_size: int = 224, batch_size: int = 16) -> Dict:
    ensure_dirs()
    train_loader, val_loader, class_to_idx = get_dataloaders(img_size=img_size, batch_size=batch_size)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = build_model(num_classes=len(class_to_idx)).to(device)

    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=lr)

    best_val_acc = 0.0
    history = {'train_loss': [], 'val_acc': []}

    for epoch in range(1, num_epochs + 1):
        model.train()
        running_loss = 0.0
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            running_loss += loss.item() * images.size(0)
        epoch_loss = running_loss / max(1, len(train_loader.dataset))

        # validation
        model.eval()
        correct = 0
        total = 0
        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.to(device)
                outputs = model(images)
                _, preds = torch.max(outputs, 1)
                correct += (preds == labels).sum().item()
                total += labels.size(0)
        val_acc = correct / max(1, total)

        history['train_loss'].append(epoch_loss)
        history['val_acc'].append(val_acc)

        if val_acc >= best_val_acc:
            best_val_acc = val_acc
            # save checkpoint
            os.makedirs(MODELS_DIR, exist_ok=True)
            torch.save({'model_state': model.state_dict(), 'class_to_idx': class_to_idx}, MODEL_PATH)
            with open(LABELS_PATH, 'w') as f:
                json.dump(class_to_idx, f)

    return {
        'best_val_acc': best_val_acc,
        'num_classes': len(class_to_idx),
        'classes': sorted(class_to_idx, key=class_to_idx.get),
        'model_path': MODEL_PATH,
        'labels_path': LABELS_PATH,
        'history': history
    }


if __name__ == '__main__':
    info = train()
    print(json.dumps(info, indent=2))
