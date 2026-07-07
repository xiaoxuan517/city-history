# 入库策略

本文说明当前多租户知识库文档处理约定。旧本地 `app.main ingest` / Chroma 入库命令已删除。

## 支持格式

当前支持:

- `.txt`
- `.md`
- `.pdf`
- `.docx`
- `.html`
- `.htm`

文档加载在 `app/retrieval/loaders.py`，切分在 `app/retrieval/splitter.py`。

## 上传路径

```text
POST /api/v1/kbs/{kb_id}/documents
  -> 保存原始文件到 UPLOAD_DIR
  -> 创建 documents 记录，status=pending
  -> 投递 Celery documents.process
```

所有文档记录都绑定 `user_id + kb_id`。

## 处理路径

```text
pending
  -> processing
  -> parse
  -> split
  -> embedding
  -> insert document_chunks
  -> completed
```

失败时:

```text
pending/processing -> failed + error_message
```

## 幂等策略

每次处理文档时，会先删除该 `document_id` 已有 chunks，再重新写入本次解析结果。这样 Celery 重试或手动同步处理不会造成重复 chunks。

## 手动处理

当 worker 暂不可用，或上传后需要本地调试时，可以调用:

```text
POST /api/v1/documents/{document_id}/process
```

该接口复用同一套处理逻辑，并仍按当前用户校验文档权限。

## 检索权限

问答检索只读取当前用户当前知识库的 chunks:

```text
document_chunks.user_id = current_user.id
document_chunks.kb_id = requested_kb_id
```

这是权限隔离的硬边界，不能改成全局召回后再过滤。
