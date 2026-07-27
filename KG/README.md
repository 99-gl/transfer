# EDA Knowledge Graph Workbench

单 Neo4j 图谱的轻量工作台：将 Excel 或 JSON 全量同步到图谱，并提供关键词与语义查询。

## 当前能力

- 上传 `.xlsx` / `.xlsm`，预览并同步当前违例 Excel 模板。
- 上传 legacy `nodes` / `edges` JSON，预览并同步到同一图谱。
- 每次提交都按稳定 UUID 创建、更新、删除记录，不执行全库清空。
- 提交后自动为 Excel/JSON 管理的节点和关系生成 embedding。
- 关键词查询、语义查询和节点详情接口。

两种格式都是全量同步：上传文件中不存在的旧导入数据会被删除。因此每次应上传完整的当前数据文件，不能仅上传增量行或局部 JSON。

## 接口

```text
POST /api/imports/preview
POST /api/imports/commit
POST /api/imports/json/preview
POST /api/imports/json/commit
POST /api/search
POST /api/semantic-search
POST /api/embeddings/rebuild
GET  /api/nodes/{uuid}
```

JSON 格式兼容原有示例：见 `data/violations_data_example.json`。

## Excel 模板

活动工作表（或指定工作表）第 3 行起的前四列：`序号`、`违例概念`、`现象`、`识别方法`。序号、违例概念和识别方法可使用纵向合并单元格。

## 运行

配置 `.env` 后，使用项目环境启动：

```bash
./.KG/bin/python -m uvicorn app.main:app --port 8000
```

打开 `http://localhost:8000`，接口文档位于 `http://localhost:8000/docs`。
