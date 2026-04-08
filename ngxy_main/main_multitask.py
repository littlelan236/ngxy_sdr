import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor

# 要运行的脚本列表
scripts = [
    # "ngxy_main/transmit_test_keys.py",
    "/home/lingweiquan/radio26/ngxy_sdr/ngxy_main/temp_test.py",
    "/home/lingweiquan/radio26/ngxy_sdr/ngxy_main/decode_key_ctrl.py",
    # ... 可继续添加
]

# 设置最大并行数（根据CPU核心数调整）
MAX_WORKERS = 4

def run_script(script_path):
    """运行单个Python脚本"""
    cmd = [sys.executable, script_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        # print(f"Success: {script_path}")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Failed: {script_path}")
        print(e.stderr)
    return script_path

if __name__ == "__main__":
    # 使用进程池并行执行
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(executor.map(run_script, scripts))