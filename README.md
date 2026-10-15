# KN5 → OBJ Converter

Converts Assetto Corsa models (`.kn5`) to `.obj` + `.mtl` and extracts their textures.

## Usage (no installation needed)

1. Download `KN5Converter.exe` from the **Releases** section.
2. Run it, add `.kn5` files or a folder, pick an output folder and click **Konwertuj**.
   - You can also drag `.kn5` files or a folder onto the `.exe`; conversion starts automatically.
3. The result: `<model>.obj`, `<model>.mtl` and a `texture/` folder (by default in an `output` subfolder next to the `.kn5` file).

The exe includes everything it needs (Python, numpy, Tkinter), so you don't need to install anything.

## Command line

```
python conv.py <folder_with_kn5>
```

## Building it yourself

```
build.bat
```
The result ends up in `dist\KN5Converter.exe`.
