"""Compact hosting uses a real source subset with the same domain contract."""
from dataclasses import asdict
import gzip,json
import pytest
from src.schemas import CatalogItem
from src import data_loader


def test_compact_profile_loads_without_expanded_source_files(tmp_path,monkeypatch):
    root=tmp_path/'compact';root.mkdir()
    books=[CatalogItem('book_one','book','A book','A journey.',page_count=None)]
    movies=[CatalogItem('movie_one','movie','A movie','Friends explore space.',runtime_minutes=95)]
    with gzip.open(root/'catalogs.json.gz','wt') as stream:
        json.dump({'book':[asdict(x) for x in books],'movie':[asdict(x) for x in movies]},stream)
    monkeypatch.setattr(data_loader,'DATA_DIR',tmp_path)
    monkeypatch.setenv('STORYSCOUT_CATALOG_PROFILE','compact')
    result=data_loader.load_active_catalogs()
    assert result['movie'][0].runtime_minutes==95
    assert result['book'][0].page_count is None
    assert result['movie'][0].source=='demo'


def test_missing_compact_snapshot_is_an_error_not_synthetic_data(tmp_path,monkeypatch):
    monkeypatch.setattr(data_loader,'DATA_DIR',tmp_path)
    monkeypatch.setenv('STORYSCOUT_CATALOG_PROFILE','compact')
    with pytest.raises(FileNotFoundError):data_loader.load_active_catalogs()
