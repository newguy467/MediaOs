# GPU converter

1. Converter → GPU setup wizard.
2. Docker: pass `--gpus all` (NVIDIA) or mount `/dev/dri` (Intel/AMD).
3. Presets use NVENC / QSV / AMF when detected.
4. Env: `HANDBRAKE_PRESET`, optional `CUDA_VISIBLE_DEVICES`.
