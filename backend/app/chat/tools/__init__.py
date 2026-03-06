from typing import Any

from app.chat.tools.catalog import list_catalog_courses as list_catalog_courses
from app.chat.tools.catalog import list_catalog_programs as list_catalog_programs
from app.chat.tools.deps import Deps as Deps
from app.chat.tools.deps import get_deps as get_deps
from app.chat.tools.deps import get_deps_with_db_templates as get_deps_with_db_templates
from app.chat.tools.document import find_document_chunks as find_document_chunks
from app.chat.tools.document import find_document_titles as find_document_titles
from app.chat.tools.document import retrieve_documents as retrieve_documents
from app.chat.tools.wordpress import list_wordpress_pages as list_wordpress_pages
from app.chat.tools.wordpress import list_wordpress_programs as list_wordpress_programs

# Public tools - available to external chatbot
PUBLIC_TOOLS: list[Any] = [
    # Document tools
    retrieve_documents,
    find_document_titles,
    find_document_chunks,
    # WordPress tools
    list_wordpress_pages,
    list_wordpress_programs,
]

# Internal tools - includes catalog tools for internal chatbot
INTERNAL_TOOLS: list[Any] = [*PUBLIC_TOOLS, list_catalog_programs, list_catalog_courses]
