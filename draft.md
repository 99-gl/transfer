curl -X POST "http://localhost:8000/tokenize" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-7B",
    "messages": [
      {"role": "user", "content": "What is the capital of France?"}
    ],
    "return_token_strs": true,
    "extra_body": {
      "chat_template_kwargs": {
        "enable_thinking": true
      }
    }
  }'
```bash
curl -sS -o /dev/null \
  --connect-timeout 5 --max-time 30 \
  -H 'Accept: application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.docker.distribution.manifest.v2+json' \
  -w 'HTTP=%{http_code} total=%{time_total}s bytes=%{size_download}\n' \
  "${MIRROR}/v2/slimerl/slime/manifests/latest"
```

常见的 Docker Hub mirror 候选（公共服务的可用性会随地区和时间变化，先执行上面的 manifest 测试再配置）：

```bash
MIRRORS=(
  'https://docker.1ms.run'
  'https://dockerproxy.net'
  'https://docker.m.daocloud.io'
)

for MIRROR in "${MIRRORS[@]}"; do
  echo "== ${MIRROR} =="
  curl -sS -o /dev/null \
    --connect-timeout 5 --max-time 30 \
    -H 'Accept: application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.docker.distribution.manifest.v2+json' \
    -w 'HTTP=%{http_code} total=%{time_total}s bytes=%{size_download}\n' \
    "${MIRROR}/v2/slimerl/slime/manifests/latest"
done
```

优先选择公司/学校或云厂商账户提供的专属 Docker Hub 加速地址（通常更稳定、带宽也更可控）；以上公共地址仅适合临时测试。测试返回 `HTTP=200` 且耗时稳定的源，再放到 `/etc/docker/daemon.json` 的 `registry-mirrors` 第一项。


wget -O /dev/null --progress=bar:force https://mirrors.huaweicloud.com/centos/7/isos/x86_64/CentOS-7-x86_64-Everything-2009.iso


jq -r '
  select(.error | contains("str_replace_editor(str_replace) requires")) |
  (.source | fromjson).messages[] |
  select(.role == "assistant") | .tool_calls[]? |
  select(
    .function.name == "str_replace_editor" and
    .function.arguments.command == "str_replace" and
    (
      (.function.arguments.old_str | type) != "string" or
      (.function.arguments.new_str | type) != "string"
    )
  ) |
  .function.arguments |
  "keys=\(keys|join(",")) old=\(.old_str|type) new=\(.new_str|type) file_text=\(.file_text|type)"
' /data/swesmith_claude_code_rejects.jsonl | sort | uniq -c


jq -r '
  select(.error | contains("str_replace_editor(create) has")) |
  (.source | fromjson).messages[] |
  select(.role == "assistant") | .tool_calls[]? |
  select(
    .function.name == "str_replace_editor" and
    .function.arguments.command == "create" and
    (.function.arguments.file_text | type) != "string"
  ) |
  .function.arguments |
  "keys=\(keys|join(",")) file_text=\(.file_text|type)"
' /data/swesmith_claude_code_rejects.jsonl




docker pull swebench/sweb.eval.x86_64.django_1776_django-11790:latest
docker pull swebench/sweb.eval.x86_64.django_1776_django-11815:latest
docker pull swebench/sweb.eval.x86_64.django_1776_django-11848:latest
docker pull swebench/sweb.eval.x86_64.django_1776_django-11880:latest
docker pull swebench/sweb.eval.x86_64.django_1776_django-11885:latest
docker pull swebench/sweb.eval.x86_64.django_1776_django-11951:latest
docker pull swebench/sweb.eval.x86_64.django_1776_django-11964:latest
docker pull swebench/sweb.eval.x86_64.django_1776_django-11999:latest
docker pull swebench/sweb.eval.x86_64.django_1776_django-12039:latest
docker pull swebench/sweb.eval.x86_64.django_1776_django-12050:latest
docker pull swebench/sweb.eval.x86_64.django_1776_django-12143:latest
docker pull swebench/sweb.eval.x86_64.django_1776_django-12155:latest
docker pull swebench/sweb.eval.x86_64.django_1776_django-12193:latest
docker pull swebench/sweb.eval.x86_64.django_1776_django-12209:latest
docker pull swebench/sweb.eval.x86_64.django_1776_django-12262:latest
docker pull swebench/sweb.eval.x86_64.django_1776_django-12273:latest
docker pull swebench/sweb.eval.x86_64.django_1776_django-12276:latest
docker pull swebench/sweb.eval.x86_64.django_1776_django-12304:latest
docker pull swebench/sweb.eval.x86_64.django_1776_django-12308:latest
docker pull swebench/sweb.eval.x86_64.django_1776_django-12325:latest
docker pull swebench/sweb.eval.x86_64.django_1776_django-12406:latest
docker pull swebench/sweb.eval.x86_64.django_1776_django-12708:latest
docker pull swebench/sweb.eval.x86_64.django_1776_django-12713:latest
docker pull swebench/sweb.eval.x86_64.django_1776_django-12774:latest
docker pull swebench/sweb.eval.x86_64.django_1776_django-9296:latest
docker pull swebench/sweb.eval.x86_64.sphinx-doc_1776_sphinx-10323:latest
docker pull swebench/sweb.eval.x86_64.sphinx-doc_1776_sphinx-10435:latest
docker pull swebench/sweb.eval.x86_64.sphinx-doc_1776_sphinx-10466:latest
docker pull swebench/sweb.eval.x86_64.sphinx-doc_1776_sphinx-10673:latest
docker pull swebench/sweb.eval.x86_64.sphinx-doc_1776_sphinx-11510:latest
docker pull swebench/sweb.eval.x86_64.sphinx-doc_1776_sphinx-7590:latest
docker pull swebench/sweb.eval.x86_64.sphinx-doc_1776_sphinx-7748:latest
docker pull swebench/sweb.eval.x86_64.sphinx-doc_1776_sphinx-7757:latest
docker pull swebench/sweb.eval.x86_64.sphinx-doc_1776_sphinx-7985:latest
docker pull swebench/sweb.eval.x86_64.sphinx-doc_1776_sphinx-8035:latest
docker pull swebench/sweb.eval.x86_64.sphinx-doc_1776_sphinx-8056:latest
docker pull swebench/sweb.eval.x86_64.sphinx-doc_1776_sphinx-8265:latest
docker pull swebench/sweb.eval.x86_64.sphinx-doc_1776_sphinx-8269:latest
docker pull swebench/sweb.eval.x86_64.sphinx-doc_1776_sphinx-8475:latest
docker pull swebench/sweb.eval.x86_64.sphinx-doc_1776_sphinx-8548:latest
docker pull swebench/sweb.eval.x86_64.sphinx-doc_1776_sphinx-8551:latest
docker pull swebench/sweb.eval.x86_64.sphinx-doc_1776_sphinx-8638:latest
docker pull swebench/sweb.eval.x86_64.sphinx-doc_1776_sphinx-8721:latest
docker pull swebench/sweb.eval.x86_64.sphinx-doc_1776_sphinx-9229:latest
docker pull swebench/sweb.eval.x86_64.sphinx-doc_1776_sphinx-9230:latest
docker pull swebench/sweb.eval.x86_64.sphinx-doc_1776_sphinx-9281:latest
docker pull swebench/sweb.eval.x86_64.sphinx-doc_1776_sphinx-9320:latest
docker pull swebench/sweb.eval.x86_64.sphinx-doc_1776_sphinx-9367:latest
docker pull swebench/sweb.eval.x86_64.sphinx-doc_1776_sphinx-9461:latest
docker pull swebench/sweb.eval.x86_64.sphinx-doc_1776_sphinx-9698:latest


cd /root/slime

PYTHONPATH=/root/slime python tools/convert_torch_dist_to_hf_parallel.py \
  --input-dir /data/checkpoints/Qwen3-Coder-30B-A3B_swesmith_sft/iter_000000XX \
  --output-dir /data/models/Qwen3-Coder-30B-A3B-swesmith-sft-hf \
  --origin-hf-dir /data/models/Qwen3-Coder-30B-A3B-Instruct \
  --load-max-workers 8 \
  --save-max-workers 16


## dsv4
```
python -c "
import importlib.metadata as m
import torch, triton, sglang

print('torch=', torch.__version__)
print('torch_cuda=', torch.version.cuda)
print('triton=', triton.__version__)
print('sglang=', sglang.__version__)

for package in [
    'sglang-kernel',
    'flashinfer-python',
    'nvidia-cutlass-dsl',
    'apache-tvm-ffi',
    'sgl-deep-gemm',
    'transformers',
]:
    try:
        print(package, '=', m.version(package))
    except m.PackageNotFoundError:
        print(package, '= MISSING')
"
```

```
nvcc --version
gcc --version | head -1
g++ --version | head -1
ninja --version
python -c "import torch; print(torch.cuda.device_count()); print([torch.cuda.get_device_capability(i) for i in range(torch.cuda.device_count())])"
```


sed -i 's/cuda-python>=13\.0/cuda-python>=12,<13/' python/pyproject.toml
sed -i 's/flashinfer_python\[cu13\]/flashinfer_python[cu12]/' python/pyproject.toml
sed -i 's/nvidia-cutlass-dsl\[cu13\]/nvidia-cutlass-dsl/' python/pyproject.toml


python -c "
import importlib.metadata as m
import torch, triton, sglang

print('torch=', torch.__version__)
print('cuda=', torch.version.cuda)
print('triton=', triton.__version__)
print('sglang=', sglang.__version__)

for p in ['sglang-kernel', 'flashinfer-python', 'nvidia-cutlass-dsl', 'apache-tvm-ffi', 'sgl-deep-gemm', 'transformers']:
    print(p, '=', m.version(p))
"

python -m pip check

### key
cd "$PATCH_ROOT"

mkdir -p secrets
umask 077
openssl rand -hex 32 > secrets/sglang_api_key
chmod 600 secrets/sglang_api_key


### start_basic
```启动
CUDA_VISIBLE_DEVICES=0,1,2,3 \
SGLANG_ROOT="$SGLANG_ROOT" \
MODEL_PATH=/models/converted/DeepSeek-V4-Flash-0731-MoE-MXFP4-BF16 \
API_KEY_FILE="$PATCH_ROOT/secrets/sglang_api_key" \
bash "$PATCH_ROOT/scripts/launch_dsv4_flash_0731_tp4.sh"
```

### test
cd "$PATCH_ROOT"

python scripts/smoke_test_api.py \
  --base-url http://127.0.0.1:30000 \
  --api-key-file secrets/sglang_api_key \
  --suite full

### start DSpark
cd "$PATCH_ROOT"
bash scripts/launch_dsv4_flash_0731_tp4_dspark.sh


## swift-megatron

```
uv pip install --upgrade-strategy only-if-needed \
  -c transfer/constraints-megatron-swift-py312-cu129.txt \
  -r transfer/requirements-megatron-swift-py312-cu129.txt

MAX_JOBS=8 uv pip install --no-build-isolation \
  --config-settings="--build-option=--cpp_ext" \
  --config-settings="--build-option=--cuda_ext" \
  "git+https://github.com/NVIDIA/apex.git@master"

MAX_JOBS=8 uv pip install --no-build-isolation "flash-attn==2.8.3"

uv pip install --editable /path/to/intern-hw/ms-swift --no-deps
```

```
python -c "import torch, apex, flash_attn, megatron.core, mcore_bridge, transformer_engine; print(torch.__version__, torch.version.cuda)"
megatron sft --help
```