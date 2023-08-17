from backend.ai.utils.github import get_repo_details, save_github_md_files_locally
from backend.ai.utils.text import chunk_file_contents
from backend.config import settings

from pinnacledb.container.document import Document
from pinnacledb.db.mongodb.query import Collection


def load_ai_artifacts(db):
    for repo_url in settings.default_repos:
        details = get_repo_details(repo_url)
        repo = details['repo']
        if repo in db.show('vector_index'):
            continue
        artifacts = _create_ai_text_artifacts(details)
        documents = [Document({settings.vector_embedding_key: v}) for v in artifacts]
        db.execute(Collection(name=repo).insert_many(documents))


def _create_ai_text_artifacts(repo_details):
    files = save_github_md_files_locally(repo_details)
    ai_text_artifacts = chunk_file_contents(files)
    return ai_text_artifacts
