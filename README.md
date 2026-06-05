# ComfyUI-Prompt-Matrix

Prompt Matrix custom nodes for ComfyUI.

The plugin focuses on one concept: a composed `prompt` string.

## Nodes

- `Prompt Matrix Source`
  - Enter one prompt candidate per line, or connect an upstream `STRING`.
  - Choose `combination` or `permutation`.
  - Set `choose_k` to control how many candidates are selected from this source.
  - Outputs a `PROMPT_MATRIX_SOURCE` object and its possibility count.

- `Prompt Matrix Controller`
  - Use `Add Source Input` to connect any number of Source nodes.
  - Outputs one composed `prompt` string, the selected global `index`, and `total`.
  - Traversal modes:
    - `random_with_repeat`: default, randomly samples with possible repeats.
    - `sequential`: walks all possibilities in order and loops.
    - `shuffle_no_repeat`: O(1) pseudo-random permutation, no repeats per cycle.

## Install

Copy `ComfyUI-Prompt-Matrix` into `ComfyUI/custom_nodes`, then restart ComfyUI.

## Tests

From this directory:

```powershell
python -m unittest discover -s tests
```
