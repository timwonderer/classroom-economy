"""
Documentation routes for Classroom Token Hub.

Serves feature-based documentation with markdown rendering,
allowing users to access help without leaving the app or losing their session.
"""

import re
from pathlib import Path
from flask import Blueprint, abort, current_app, session, request, url_for, redirect, make_response
from werkzeug.exceptions import HTTPException
from werkzeug.utils import safe_join
import bleach
import markdown
import yaml
from markdown.extensions.toc import TocExtension
from markdown.extensions.codehilite import CodeHiliteExtension
from markdown.extensions.fenced_code import FencedCodeExtension
from markdown.extensions.tables import TableExtension
from urllib.parse import urlparse

from app.utils.helpers import (
    docs_url_for,
    render_template_with_fallback,
    should_redirect_public_docs,
)

# Create blueprint
docs_bp = Blueprint('docs', __name__, url_prefix='/docs')

# Documentation root directory
DOCS_ROOT = Path(__file__).parent.parent.parent / 'docs'

# Directories excluded from ALL search audiences (internal documentation only)
EXCLUDED_DIRECTORIES = {'security'}

# Friendly category names for search results
CATEGORY_MAP = {
    'ARCHITECTURE': 'Architecture',
    'DOMAINS': 'Domains',
    'FEATURES': 'Features',
    'LOGS': 'Logs',
    'SECURITY': 'Security',
    'STANDARD_OPERATING_PROCEDURES': 'Standard Operating Procedures',
    'TESTING': 'Testing',
    'SPECS': 'Specs',
    'TRACKING': 'Tracking',
    'DOMAIN': 'Domain',
    'FEATURE-EXECUTION': 'Feature Execution',
    'INVARIANT': 'Invariant',
    'MAP': 'Map',
    'ARCHITECTURE': 'Architecture',
    'self-hosting': 'Self Hosting',
    'archive': 'Archive'
}

# HTML sanitization configuration for rendered markdown
DOCS_ALLOWED_TAGS = [
    'p', 'br', 'span', 'div',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'strong', 'em', 'u', 's', 'del', 'code', 'pre',
    'ul', 'ol', 'li',
    'a', 'img',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'blockquote', 'hr',
]
DOCS_ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'rel'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
    'code': ['class'],
    'pre': ['class'],
    'span': ['class'],
    'div': ['class'],
    'table': ['class'],
    'thead': ['class'],
    'tbody': ['class'],
    'tr': ['class'],
    'th': ['align', 'class'],
    'td': ['align', 'class'],
    'ul': ['class'],
    'ol': ['class'],
    'li': ['class'],
    'h1': ['id', 'class'],
    'h2': ['id', 'class'],
    'h3': ['id', 'class'],
    'h4': ['id', 'class'],
    'h5': ['id', 'class'],
    'h6': ['id', 'class'],
}
DOCS_ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']

# Configuration for GitHub-style alert callouts.  Keyed by the alert type
# keyword (upper-case) as it appears between [! … ] in the source.
_ALERT_CONFIG = {
    'NOTE':      {'icon': 'info',          'label': 'Note'},
    'TIP':       {'icon': 'lightbulb',     'label': 'Tip'},
    'IMPORTANT': {'icon': 'priority_high', 'label': 'Important'},
    'WARNING':   {'icon': 'warning',       'label': 'Warning'},
    'CAUTION':   {'icon': 'dangerous',     'label': 'Caution'},
}

# Compiled regex that matches the opening line of a GitHub-style alert
# blockquote, e.g. "> [!NOTE]" or "> [!WARNING] optional inline text".
_ALERT_START = re.compile(
    r'^>\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*(.*)$',
    re.IGNORECASE,
)


def _redirect_to_public_docs(doc_path=None):
    target = docs_url_for(doc_path)
    parsed = urlparse(target)
    if parsed.scheme in ("http", "https"):
        configured_base = current_app.config.get("EXTERNAL_DOCS_BASE_URL", "").rstrip("/")
        configured_parsed = urlparse(configured_base) if configured_base else None
        normalized_base_path = configured_parsed.path.rstrip("/") if configured_parsed else ""
        target_path = parsed.path.rstrip("/")
        if (
            not configured_parsed
            or parsed.scheme != configured_parsed.scheme
            or parsed.netloc != configured_parsed.netloc
            or not (
                target_path == normalized_base_path
                or target_path.startswith(f"{normalized_base_path}/")
            )
        ):
            abort(404)
    elif parsed.scheme or parsed.netloc:
        abort(404)
    return redirect(target)


def parse_front_matter(content):
    """
    Extract YAML-style front matter from markdown content using PyYAML.

    Front matter format:
    ---
    title: Page Title
    category: feature-name
    roles: [teacher, student]
    related:
      - path/to/related/doc
      - another/related/doc
    ---

    Returns:
        tuple: (metadata_dict, remaining_content)
    """
    if not content.startswith('---'):
        return {}, content

    try:
        # Split on '---' delimiter
        parts = content.split('---', 2)
        if len(parts) < 3:
            return {}, content

        # Parse YAML front matter using PyYAML
        front_matter = parts[1].strip()
        # Only treat as front matter if at least one line looks like "key: value".
        # This avoids false positives on markdown that starts with horizontal rules.
        has_yaml_key = any(
            re.match(r"^\s*[A-Za-z_][A-Za-z0-9_-]*\s*:", line)
            for line in front_matter.splitlines()
            if line.strip()
        )
        if not has_yaml_key:
            return {}, content
        metadata = yaml.safe_load(front_matter) or {}

        # Ensure metadata is a dictionary
        if not isinstance(metadata, dict):
            current_app.logger.warning(f"Front matter is not a dict: {type(metadata)}")
            return {}, content

        return metadata, parts[2].strip()
    except yaml.YAMLError as e:
        current_app.logger.warning(f"Failed to parse YAML front matter: {e}")
        return {}, content
    except Exception as e:
        current_app.logger.warning(f"Unexpected error parsing front matter: {e}")
        return {}, content


def preprocess_github_alerts(content):
    """
    Pre-process markdown source to convert GitHub-style blockquote alerts
    into styled HTML callout blocks before the main markdown renderer runs.

    This avoids a Python markdown library limitation where adjacent blockquotes
    separated by a blank line are merged into a single ``<blockquote>`` element.
    By converting alerts here (from the raw markdown source), each alert is
    handled independently, regardless of what surrounds it.

    The alert body text is rendered through a lightweight markdown pass so
    that inline and block markup (bold, code, links, nested lists, etc.) is
    fully converted to HTML before being embedded in the output.  The main
    renderer then sees the surrounding ``<div>`` elements as raw HTML blocks
    and passes them through unchanged.

    Supported syntax (identical to GitHub Flavored Markdown)::

        > [!NOTE]
        > Informational callout.

        > [!TIP]
        > **Bold** text and ``code`` work inside the body.

        > [!IMPORTANT]
        > First paragraph.
        >
        > Second paragraph.

    Supported types: NOTE, TIP, IMPORTANT, WARNING, CAUTION
    """
    lines = content.split('\n')
    out = []
    i = 0

    while i < len(lines):
        m = _ALERT_START.match(lines[i])
        if m:
            alert_type = m.group(1).upper()
            first_text = m.group(2).strip()
            config = _ALERT_CONFIG[alert_type]

            # Collect the remaining continuation lines of this blockquote.
            # Any line whose left-stripped form starts with '>' continues the
            # blockquote (covers "> text", ">text", ">\ttext", ">   ", etc.).
            # A line that does NOT start with '>' (after lstrip) ends the alert.
            body_lines = []
            if first_text:
                body_lines.append(first_text)

            i += 1
            while i < len(lines):
                raw = lines[i]
                stripped = raw.lstrip()
                if stripped.startswith('>'):
                    # Strip the leading '>' and exactly one optional space or
                    # tab per the blockquote spec.  Using lstrip(' \t') would
                    # remove multiple leading spaces and break indented code
                    # blocks inside the alert body.
                    after_marker = stripped[1:]
                    if after_marker and after_marker[0] in (' ', '\t'):
                        after_marker = after_marker[1:]
                    # A remainder that is empty or all-whitespace is a blank
                    # line separating paragraphs within the alert body.
                    body_lines.append(after_marker if after_marker.strip() else '')
                    i += 1
                else:
                    break

            body_text = '\n'.join(body_lines).strip()

            # Render the alert body through a lightweight markdown pass so
            # that bold, code, links, and other markup are converted to HTML.
            # Using a separate instance avoids polluting the main TOC / state.
            body_md = markdown.Markdown(extensions=['extra', FencedCodeExtension()])
            body_html = body_md.convert(body_text) if body_text else ''

            # Emit a self-contained HTML block.  The main renderer treats
            # block-level HTML elements (divs starting at column 0) as raw
            # blocks and passes them through unchanged.
            alert_html = (
                f'<div class="md-alert md-alert-{alert_type.lower()}">'
                f'<div class="md-alert-header">'
                f'<span class="material-symbols-outlined md-alert-icon">'
                f'{config["icon"]}</span>'
                f'<span class="md-alert-label">{config["label"]}</span>'
                f'</div>'
                f'<div class="md-alert-body">{body_html}</div>'
                f'</div>'
            )
            out.append(alert_html)
            out.append('')
        else:
            out.append(lines[i])
            i += 1

    return '\n'.join(out)


def render_markdown_content(content, toc_title='On This Page'):
    """
    Convert markdown to HTML with extensions and sanitization.

    Args:
        content: Markdown text
        toc_title: The title for the Table of Contents.

    Returns:
        tuple: (sanitized_html_content, sanitized_toc_html)

    Note: The 'nl2br' extension is intentionally omitted to avoid unexpected
    line breaks in formatted content like code blocks and tables. Standard
    markdown requires two spaces at the end of a line or a blank line for breaks.
    """
    # Pre-process GitHub-style alerts before the markdown library sees them.
    # This must happen first so adjacent alerts are not merged into a single
    # blockquote by Python's markdown parser.
    content = preprocess_github_alerts(content)

    md = markdown.Markdown(
        extensions=[
            'extra',
            TocExtension(title=toc_title, toc_depth='2-6'),
            CodeHiliteExtension(linenums=False, css_class='highlight'),
            FencedCodeExtension(),
            TableExtension(),
        ]
    )

    html = md.convert(content)
    toc = md.toc if hasattr(md, 'toc') else ''

    # Sanitize HTML to prevent XSS
    cleaner = bleach.Cleaner(
        tags=DOCS_ALLOWED_TAGS,
        attributes=DOCS_ALLOWED_ATTRIBUTES,
        protocols=DOCS_ALLOWED_PROTOCOLS,
        strip=True,
        strip_comments=True,
    )

    return cleaner.clean(html), cleaner.clean(toc)


def build_breadcrumbs(doc_path, docs_root):
    """
    Build breadcrumb navigation for documentation pages.

    Args:
        doc_path: Full documentation path without extension
        docs_root: Root docs directory

    Returns:
        list: List of dicts with 'title' and 'url' keys
    """
    parts = Path(doc_path).parts
    breadcrumbs = []

    # Build intermediate directory crumbs. Only make them clickable
    # when an index markdown file actually exists at that path.
    for idx, part in enumerate(parts[:-1]):
        partial_path = "/".join(parts[:idx + 1])
        partial_file = docs_root / f"{partial_path}.md"
        partial_index = docs_root / partial_path / "index.md"
        partial_readme = docs_root / partial_path / "README.md"
        has_landing_doc = partial_file.exists() or partial_index.exists() or partial_readme.exists()
        breadcrumbs.append({
            'title': part.replace('-', ' ').replace('_', ' ').title(),
            'url': url_for('docs.view_doc', doc_path=partial_path) if has_landing_doc else None
        })

    # Current page crumb (always the last item, rendered as active text in template)
    if parts:
        breadcrumbs.append({
            'title': parts[-1].replace('-', ' ').replace('_', ' ').title(),
            'url': None
        })

    return breadcrumbs


# -------------------- ROUTES --------------------

def get_docs_audience():
    """Determine the documentation audience ('user' or 'devops') for the current request."""
    from app.auth import get_current_admin, get_current_seat, get_current_user

    # Active teacher/student session enforces 'user' mode
    if (
        get_current_admin() is not None
        or get_current_seat() is not None
        or get_current_user() is not None
    ):
        return 'user'
    
    # Otherwise respect the chosen cookie
    audience = request.cookies.get('docs_audience')
    if audience in ['user', 'devops']:
        return audience
        
    # Sysadmins default to 'devops'
    if session.get('is_system_admin') and session.get('sysadmin_id'):
        return 'devops'
        
    # Default public audience
    return 'user'

@docs_bp.route('/set-audience')
def set_audience():
    """Toggle between 'user' and 'devops' documentation."""
    allowed_audiences = {'user', 'devops'}
    audience_arg = (request.args.get('aud') or '').strip().lower()
    audience = audience_arg if audience_arg in allowed_audiences else 'user'

    # Always redirect to docs index after toggle to avoid any untrusted redirect target.
    next_url = url_for('docs.index')

    resp = make_response(redirect(next_url))
    resp.set_cookie(
        'docs_audience',
        audience,
        max_age=31536000,  # 1 year
        httponly=True,
        samesite='Lax',
        secure=request.is_secure,
    )
    return resp
    

@docs_bp.route('/')
def index():
    """Documentation homepage with categories."""
    if should_redirect_public_docs():
        return _redirect_to_public_docs()

    audience = get_docs_audience()
    return render_template_with_fallback('docs/index.html', audience=audience)


@docs_bp.route('/timeline')
def timeline():
    """Interactive project development timeline."""
    if should_redirect_public_docs('timeline'):
        return _redirect_to_public_docs('timeline')

    return render_template_with_fallback('docs/timeline.html')


@docs_bp.route('/<path:doc_path>')
def view_doc(doc_path):
    """
    Render a markdown documentation file as HTML.

    URL structure:
    - /docs/getting-started/overview
    - /docs/store/creating-basic-items
    - /docs/technical-reference/architecture

    Args:
        doc_path: Path to the documentation file (without .md extension)
    """
    if should_redirect_public_docs(doc_path):
        return _redirect_to_public_docs(doc_path)

    # Security: Validate input and prevent directory traversal
    try:
        # Normalize basic string form and reject empty/whitespace-only paths
        doc_path = (doc_path or "").strip()
        if not doc_path:
            current_app.logger.warning("Empty doc path")
            abort(404)

        # Reject paths with suspicious characters
        if not re.fullmatch(r"[A-Za-z0-9_./-]+", doc_path):
            current_app.logger.warning(f"Invalid characters in doc path: {doc_path}")
            abort(404)

        def resolve_doc_path(untrusted_path: str, docs_root: Path) -> Path:
            """
            Resolve an untrusted documentation path to a safe file within docs_root.

            Security validation strategy:
            1. Reject absolute paths and '..' components
            2. Build allowed candidate files (.md, /index.md, /README.md)
            3. Resolve each candidate path and ensure it remains under docs root
            """
            # Normalize the untrusted path as a relative path
            safe_rel_path = Path(untrusted_path)

            # Reject absolute paths, traversal components, or attempts to escape the root
            if safe_rel_path.is_absolute() or any(part == ".." for part in safe_rel_path.parts):
                current_app.logger.warning(f"Path traversal attempt: {untrusted_path}")
                abort(404)

            # Ensure docs_root is absolute and normalized and actually exists
            try:
                root_resolved = docs_root.resolve(strict=True)
            except OSError as e:
                current_app.logger.error(f"Invalid DOCS_ROOT '{docs_root}': {e}")
                abort(500)

            # Build candidate paths under documentation root.
            try:
                safe_candidate = safe_join(str(root_resolved), *safe_rel_path.parts)
                if not safe_candidate:
                    current_app.logger.warning(f"Path escaped DOCS_ROOT: {untrusted_path}")
                    abort(404)

                candidate_base = Path(safe_candidate)
                if candidate_base.suffix and candidate_base.suffix.lower() != '.md':
                    current_app.logger.warning(f"Unsupported docs suffix in path: {untrusted_path}")
                    abort(404)

                if candidate_base.suffix.lower() == '.md':
                    candidates = [candidate_base]
                else:
                    candidates = [
                        Path(f"{candidate_base}.md"),
                        candidate_base / "index.md",
                        candidate_base / "README.md",
                    ]
            except OSError as e:
                current_app.logger.warning(f"Error resolving documentation path '{untrusted_path}': {e}")
                abort(404)

            # Resolve candidate paths and pick the first existing file inside docs root.
            selected_candidate = None
            for candidate in candidates:
                resolved_candidate = candidate.resolve(strict=False)
                try:
                    resolved_candidate.relative_to(root_resolved)
                except ValueError:
                    current_app.logger.warning(f"Path outside DOCS_ROOT: {untrusted_path}")
                    abort(404)

                if candidate.exists():
                    selected_candidate = resolved_candidate
                    break

            if selected_candidate is None:
                selected_candidate = candidates[0].resolve(strict=False)

            # Path has been validated through multiple layers:
            # 1. Earlier regex validation of the docs path blocks suspicious characters
            # 2. The component check in this function blocks absolute paths and '..' traversal
            # 3. The resolved path verification above ensures containment within the docs root
            return selected_candidate

        # Ensure we have a safe, absolute docs root
        try:
            docs_root = DOCS_ROOT
        except NameError:
            # Fallback: constrain to a 'docs' directory under the application root
            docs_root = Path(current_app.root_path) / "docs"
        # Make sure docs_root is a Path instance
        if not isinstance(docs_root, Path):
            docs_root = Path(docs_root)
        doc_file = resolve_doc_path(doc_path, docs_root)




        if not doc_file.exists():
            current_app.logger.info(f"Documentation not found: {doc_path}")
            abort(404)

        # Canonicalize directory-style docs URLs so relative markdown links resolve
        # under the directory (e.g. /docs/DOMAIN/DOM-CORE-001/).
        if doc_file.name.lower() in {'index.md', 'readme.md'}:
            canonical_path = re.sub(
                r'/(?:index|readme)(?:\.md)?/?$',
                '/',
                request.path,
                flags=re.IGNORECASE,
            )
            if canonical_path == request.path and not request.path.endswith('/'):
                canonical_path = f"{request.path}/"

            if canonical_path != request.path:
                query = f"?{request.query_string.decode('utf-8')}" if request.query_string else ""
                target = f"{canonical_path}{query}"
                # Ensure redirect target is a relative URL without scheme or netloc
                target = target.replace('\\', '')
                parsed = urlparse(target)
                if parsed.scheme or parsed.netloc:
                    current_app.logger.warning(
                        "Blocked unsafe redirect attempt to %r from path %r",
                        target, request.path
                    )
                else:
                    return redirect(target, code=301)

        # Read and parse the file
        try:
            content = doc_file.read_text(encoding='utf-8')
        except UnicodeDecodeError as e:
            current_app.logger.error(f"File encoding error for {doc_path}: {e}")
            abort(500, description="Unable to read documentation file (encoding error)")

        metadata, body = parse_front_matter(content)
        doc_title = metadata.get('title', doc_path)

        # Convert markdown to HTML (with sanitization)
        html_content, toc = render_markdown_content(body, toc_title=doc_title)

        # Determine category from path
        path_parts = Path(doc_path).parts
        category = path_parts[0] if path_parts else None

        # Build breadcrumbs
        breadcrumbs = build_breadcrumbs(doc_path, docs_root)

        # Get related articles if specified in front matter
        related_articles = []
        if 'related' in metadata:
            related_paths = metadata['related']
            if isinstance(related_paths, str):
                related_paths = [related_paths]

            for rel_path in related_paths:
                try:
                    # Remove leading slash and ensure proper path
                    rel_path = rel_path.lstrip('/')
                    related_articles.append({
                        'title': rel_path.replace('/', ' / ').replace('-', ' ').replace('_', ' ').title(),
                        'url': docs_url_for(rel_path)
                    })
                except Exception as e:
                    current_app.logger.warning(f"Error processing related article {rel_path}: {e}")

        # Get user role for UI filtering
        # Note: Role-based filtering is for UI display only, not access control.
        # All documentation is accessible to all users. The 'roles' metadata
        # is used for contextual highlighting and navigation suggestions.
        from app.auth import get_current_admin, get_current_seat

        user_role = None
        current_admin = get_current_admin()
        current_seat = get_current_seat()
        if current_admin is not None:
            user_role = 'teacher'
        elif current_seat is not None:
            user_role = 'student'
        elif session.get('is_system_admin') and session.get('sysadmin_id'):
            user_role = 'sysadmin'

        audience = get_docs_audience()
        
        return render_template_with_fallback(
            'docs/view.html',
            content=html_content,
            toc=toc,
            title=doc_title,
            category=category,
            current_category=category,
            breadcrumbs=breadcrumbs,
            roles=metadata.get('roles', []),
            related=related_articles,
            user_role=user_role,
            doc_path=doc_path,
            audience=audience,
        )

    except HTTPException:
        raise
    except (OSError, IOError) as e:
        current_app.logger.error(f"File system error rendering {doc_path}: {e}")
        abort(500, description="Unable to access documentation file")
    except Exception as e:
        current_app.logger.exception(f"Unexpected error rendering documentation: {e}")
        abort(500)


@docs_bp.route('/search')
def search():
    """
    Documentation search with relevance scoring and filtering.

    Searches through documentation files for the query string,
    excluding internal-only documentation and ranking results by relevance.

    Metadata support:
    - searchable: false - Excludes document from search results
    - keywords: [...] - Additional searchable terms for better matching
    - description: "..." - Used for search context and relevance
    """
    if should_redirect_public_docs('search'):
        return _redirect_to_public_docs('search')

    query = request.args.get('q', '').strip()
    audience = get_docs_audience()

    if not query:
        return render_template_with_fallback('docs/search.html', query='', results=[], audience=audience)

    results = []
    query_lower = query.lower()
    query_words = set(query_lower.split())

    try:
        # Search through all markdown files
        # Note: This implementation reads all files on every search request.
        # For production with many documentation files, consider implementing
        # a search index (in-memory or cached) built at startup for better performance.
        for doc_file in DOCS_ROOT.rglob('*.md'):
            try:
                # Skip if not relative to DOCS_ROOT (safety check)
                if not doc_file.is_relative_to(DOCS_ROOT.resolve()):
                    continue

                rel_path = doc_file.relative_to(DOCS_ROOT)

                # Enforce audience context directory filtering
                top_dir_raw = rel_path.parts[0] if rel_path.parts else ''
                top_dir = top_dir_raw.lower()
                
                # Skip excluded directories (internal docs)
                if top_dir in EXCLUDED_DIRECTORIES:
                    continue
                if 'ai' in rel_path.parts:
                    continue
                    
                # Strict audience isolation
                is_archived_user_guide = "v1-user-guides" in doc_file.parts
                if audience == 'user':
                    if not is_archived_user_guide:
                        continue
                else:
                    if is_archived_user_guide:
                        continue

                content = doc_file.read_text(encoding='utf-8')
                metadata, body = parse_front_matter(content)

                # Skip if explicitly marked as not searchable
                if metadata.get('searchable', True) is False:
                    continue

                # Get metadata fields for relevance scoring
                title = metadata.get('title', doc_file.stem)
                description = metadata.get('description', '').strip()
                keywords = metadata.get('keywords', []) or []
                if not isinstance(keywords, list):
                    keywords = [str(keywords)] if keywords else []

                # Calculate relevance score
                relevance_score = 0

                # Title match (highest priority - 10 points)
                if query_lower in title.lower():
                    relevance_score += 10
                    # Exact title match gets bonus
                    if query_lower == title.lower():
                        relevance_score += 5

                # Keyword match (high priority - 8 points per keyword)
                for keyword in keywords:
                    if query_lower in keyword.lower():
                        relevance_score += 8

                # Description match (medium priority - 5 points)
                if description and query_lower in description.lower():
                    relevance_score += 5

                # Body match (lower priority - 1 point, max 3)
                body_matches = body.lower().count(query_lower)
                relevance_score += min(body_matches, 3)

                # Word-based relevance (check if query words appear)
                title_words = set(title.lower().split())
                keyword_words = {word for keyword in keywords for word in keyword.lower().split()}
                desc_words = set(description.lower().split()) if description else set()

                # Bonus for word matches
                word_matches_in_title = len(query_words & title_words)
                word_matches_in_keywords = len(query_words & keyword_words)
                word_matches_in_desc = len(query_words & desc_words)

                relevance_score += word_matches_in_title * 3
                relevance_score += word_matches_in_keywords * 2
                relevance_score += word_matches_in_desc * 1

                # Only include results with positive relevance
                if relevance_score > 0:
                    # Get relative path for URL
                    rel_path_no_ext = rel_path.with_suffix('')

                    # Find context around the match
                    context = ''

                    # Prefer description as context if available
                    if description:
                        context = description[:200]
                    else:
                        # Find first line with query match
                        for line in body.split('\n'):
                            if query_lower in line.lower():
                                context = line.strip()[:200]
                                break

                        # Fallback: first non-empty line
                        if not context:
                            for line in body.split('\n'):
                                stripped = line.strip()
                                if stripped and not stripped.startswith('#'):
                                    context = stripped[:200]
                                    break

                    # Determine category display name
                    category = 'Other'
                    if rel_path.parts:
                        category_key = rel_path.parts[0]
                        category = CATEGORY_MAP.get(
                            category_key,
                            CATEGORY_MAP.get(category_key.lower(), category_key.replace('-', ' ').replace('_', ' ').title())
                        )

                    results.append({
                        'title': title,
                        'url': docs_url_for(str(rel_path_no_ext.as_posix())),
                        'context': context,
                        'category': category,
                        'relevance': relevance_score
                    })

            except (UnicodeDecodeError, OSError, IOError) as e:
                current_app.logger.warning(f"Error reading file {doc_file}: {e}")
                continue
            except Exception as e:
                current_app.logger.warning(f"Unexpected error searching {doc_file}: {e}")
                continue

        # Sort results by relevance (highest first)
        results.sort(key=lambda x: x['relevance'], reverse=True)

    except (OSError, IOError) as e:
        current_app.logger.error(f"File system error during search: {e}")
    except Exception as e:
        current_app.logger.exception(f"Unexpected error during search: {e}")

    return render_template_with_fallback(
        'docs/search.html',
        query=query,
        results=results,
        audience=audience
    )
