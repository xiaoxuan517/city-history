from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.config.settings import settings


class AListFileListRequest(BaseModel):
    path: str = settings.gazetteer_file_root_path
    password: str = ""
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=100, ge=1)
    refresh: bool = False


class AListHashInfo(BaseModel):
    md5: str | None = None


class AListLabel(BaseModel):
    id: int
    type: int
    name: str
    create_time: str


class AListFileItem(BaseModel):
    id: str
    path: str
    virtual_path: str | None = None
    name: str
    size: int
    is_dir: bool
    modified: str
    created: str
    sign: str
    thumb: str
    type: int
    hashinfo: str
    hash_info: AListHashInfo | None = None
    label_list: list[AListLabel] | None = None


class AListFileListData(BaseModel):
    content: list[AListFileItem]
    total: int
    readme: str
    header: str
    write: bool
    provider: str


class AListFileListResponse(BaseModel):
    code: int
    message: str
    data: AListFileListData


class AListOfflineDownloadRequest(BaseModel):
    path: str = "downloads"
    urls: list[str] | None = None
    source_path: str | None = None
    list_path: str | None = None
    name: str | None = None
    tool: str = "SimpleHttp"
    delete_policy: str = "delete_on_upload_succeed"

    @model_validator(mode="after")
    def validate_source(self) -> "AListOfflineDownloadRequest":
        if not self.urls and not self.source_path and not (self.list_path and self.name):
            raise ValueError("One of urls, source_path, or list_path + name is required")
        return self


class AListTask(BaseModel):
    id: str = ""
    name: str = ""
    state: int = 0
    status: str = ""
    progress: int = 0
    error: str = ""


class AListOfflineDownloadData(BaseModel):
    tasks: list[AListTask]


class AListOfflineDownloadResponse(BaseModel):
    code: int
    message: str
    data: AListOfflineDownloadData


class AListTaskListRequest(BaseModel):
    task_ids: list[str] = Field(default_factory=list)


class AListTaskListResponse(BaseModel):
    code: int
    message: str
    data: AListOfflineDownloadData


class AListRawResponse(BaseModel):
    code: int
    message: str
    data: dict[str, Any] | None = None
