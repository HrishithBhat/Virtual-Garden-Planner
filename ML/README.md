# Plant Disease Detection (ML)

This module provides training and inference for a simple image classifier that detects plant diseases from leaf photos.

## Folder Structure

- dataset/ — training images organized in subfolders per class (disease name)
  - Example:
    - dataset/
      - healthy/
      - leaf_blight/
      - rust/
- models/
  - latest.pt — trained PyTorch model
  - labels.json — mapping of class names to indices
- train.py — training script (transfer learning on ResNet18)
- inference.py — model loading and prediction utilities

## How Training Works

- You (Admin) upload photos in the Admin Panel → ML Training page, selecting a class name.
- Images are saved under dataset/<class_name>/.
- Clicking "Train Model" runs a short training job (transfer learning) and saves artifacts into models/.

## Manual Training (optional)

1. Add images into dataset/<class_name>/ subfolders.
2. Run:
   
   ```bash
   python -m ML.train
   ```

3. Artifacts will be generated in models/.

## Tips for Good Results

- Aim for at least 50–100 images per class.
- Use diverse angles/lighting and both healthy and diseased samples.
- Keep class names simple (e.g., healthy, rust, blight).

## Inference

- The app uses ML/inference.py to load models/models/latest.pt and predict from uploaded images.
- Endpoint: POST /api/ai/disease/predict with form-data field "image".

