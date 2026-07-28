from datasets import load_dataset

# 只加载 'tool' 分片以节省时间和带宽
dataset = load_dataset("SWE-bench/SWE-smith-trajectories", split="tool")

# 筛选出 model 为 'claude-3.7-sonnet' 且 resolved 为 True 的数据
filtered_dataset = dataset.filter(lambda x: x["model"] == "claude-3.7-sonnet" and x["resolved"] == True)

# 查看筛选后的数据量
print(len(filtered_dataset))