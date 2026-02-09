# YOLO Dataset Validation Suite

This repository contains two specialized Python GUI tools designed to streamline the process of validating and editing YOLO-formatted object detection datasets. These tools were developed to bridge the gap between automated labeling and high-quality "gold standard" datasets.

## 🚀 The Tools

### 1. YOLO Validator V30 (Box-Wise/Flashcard Mode)
**Filename:** `data_annotator_validating_box_wise.py`

This tool is optimized for ultra-fast verification of large datasets. It treats every bounding box as a "flashcard," automatically zooming into and centering each object one by one.

* **Box-Wise Navigation:** Use `Space` or `Right Arrow` to cycle through every individual box in the dataset.
* **Auto-Zoom:** Automatically calculates the optimal zoom level to focus on the active object.
* **Global Box Jump:** Jump to specific box IDs across the entire dataset.
* **Undo/Redo System:** Full support for `Ctrl+Z` and `Ctrl+Y` to revert accidental deletions or class changes.
* **Auto-Suggest Search:** Quickly change classes with an intelligent search dialog.

### 2. YOLO Validator V18 (Full-Image Editor)
**Filename:** `data_annotator_validating_tool.py`

A comprehensive image-level editor designed for contextual validation. It allows you to see all objects within an image simultaneously and perform bulk edits.

* **Dual Mode:** Toggle between `EDIT` and `DRAW` modes to modify existing boxes or add missing ones.
* **Enhanced Panning:** Use `Shift + Left Click` or `Middle Mouse` to pan across high-resolution images.
* **Visual Legend:** A sidebar displaying active object counts and a full class ID legend.
* **Red-Text Overlay:** High-visibility class ID rendering for quick visual confirmation.

## 🛠️ Installation

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/Willayat060/YOLO-Validation-Tools.git](https://github.com/Willayat060/Data_annotating_tool.git)
   cd data_annotating_tool
