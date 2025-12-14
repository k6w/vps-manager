"""
Version Control and Backup System
Git-like version control for VPS configurations with project-oriented features
"""

import json
import shutil
import hashlib
import tarfile
import difflib
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

from .utils import get_logger, MANAGER_DIR, NGINX_SITES_DIR

logger = get_logger(__name__)


@dataclass
class Commit:
    """Represents a configuration commit (like git commit)"""
    hash: str
    timestamp: str
    author: str
    message: str
    description: str
    tags: List[str]
    parent: Optional[str]
    files_changed: List[str]
    domains_snapshot: Dict
    config_snapshot: Dict
    stats: Dict  # lines added/removed, files modified, etc.
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict):
        return cls(**data)
    
    def short_hash(self) -> str:
        """Get short hash (first 7 chars like git)"""
        return self.hash[:7]


@dataclass
class Branch:
    """Represents a configuration branch"""
    name: str
    current_commit: str
    created_at: str
    description: str
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict):
        return cls(**data)


class VersionControl:
    """Git-like version control for VPS Manager"""
    
    def __init__(self, manager):
        self.manager = manager
        self.vcs_dir = MANAGER_DIR / "vcs"
        self.commits_dir = self.vcs_dir / "commits"
        self.branches_dir = self.vcs_dir / "branches"
        self.tags_dir = self.vcs_dir / "tags"
        self.objects_dir = self.vcs_dir / "objects"
        
        self.commits_file = self.vcs_dir / "commits.json"
        self.branches_file = self.vcs_dir / "branches.json"
        self.head_file = self.vcs_dir / "HEAD"
        
        self._init_repository()
    
    def _init_repository(self):
        """Initialize version control repository"""
        # Create directory structure
        for directory in [self.vcs_dir, self.commits_dir, self.branches_dir, 
                         self.tags_dir, self.objects_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Initialize commits list
        if not self.commits_file.exists():
            with open(self.commits_file, 'w') as f:
                json.dump([], f)
        
        # Initialize branches
        if not self.branches_file.exists():
            main_branch = Branch(
                name="main",
                current_commit="",
                created_at=datetime.now().isoformat(),
                description="Main configuration branch"
            )
            with open(self.branches_file, 'w') as f:
                json.dump([main_branch.to_dict()], f, indent=2)
        
        # Initialize HEAD
        if not self.head_file.exists():
            with open(self.head_file, 'w') as f:
                f.write("main")
        
        logger.info("Version control repository initialized")
    
    def _generate_hash(self, content: str) -> str:
        """Generate hash for content (like git SHA-1)"""
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _get_current_branch(self) -> str:
        """Get current branch name"""
        if self.head_file.exists():
            with open(self.head_file, 'r') as f:
                return f.read().strip()
        return "main"
    
    def _set_current_branch(self, branch_name: str):
        """Set current branch"""
        with open(self.head_file, 'w') as f:
            f.write(branch_name)
    
    def _load_commits(self) -> List[Commit]:
        """Load all commits"""
        try:
            with open(self.commits_file, 'r') as f:
                data = json.load(f)
                return [Commit.from_dict(c) for c in data]
        except Exception as e:
            logger.error(f"Failed to load commits: {e}")
            return []
    
    def _save_commits(self, commits: List[Commit]):
        """Save commits to file"""
        try:
            with open(self.commits_file, 'w') as f:
                json.dump([c.to_dict() for c in commits], f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save commits: {e}")
    
    def _load_branches(self) -> List[Branch]:
        """Load all branches"""
        try:
            with open(self.branches_file, 'r') as f:
                data = json.load(f)
                return [Branch.from_dict(b) for b in data]
        except Exception as e:
            logger.error(f"Failed to load branches: {e}")
            return []
    
    def _save_branches(self, branches: List[Branch]):
        """Save branches to file"""
        try:
            with open(self.branches_file, 'w') as f:
                json.dump([b.to_dict() for b in branches], f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save branches: {e}")
    
    def _capture_current_state(self) -> Dict:
        """Capture current configuration state"""
        state = {
            "domains": [d.to_dict() for d in self.manager.domains],
            "config": self.manager.config.copy(),
            "nginx_configs": {},
            "timestamp": datetime.now().isoformat()
        }
        
        # Capture NGINX configs
        for domain in self.manager.domains:
            config_file = NGINX_SITES_DIR / domain.name
            if config_file.exists():
                with open(config_file, 'r') as f:
                    state["nginx_configs"][domain.name] = f.read()
        
        return state
    
    def _calculate_diff(self, old_state: Dict, new_state: Dict) -> Dict:
        """Calculate diff between two states"""
        stats = {
            "domains_added": 0,
            "domains_removed": 0,
            "domains_modified": 0,
            "configs_changed": 0,
            "settings_changed": 0
        }
        
        old_domains = {d['name']: d for d in old_state.get('domains', [])}
        new_domains = {d['name']: d for d in new_state.get('domains', [])}
        
        # Check domains
        old_names = set(old_domains.keys())
        new_names = set(new_domains.keys())
        
        stats["domains_added"] = len(new_names - old_names)
        stats["domains_removed"] = len(old_names - new_names)
        
        # Check modifications
        for name in old_names & new_names:
            if old_domains[name] != new_domains[name]:
                stats["domains_modified"] += 1
        
        # Check config changes
        old_configs = old_state.get('nginx_configs', {})
        new_configs = new_state.get('nginx_configs', {})
        
        for name in set(old_configs.keys()) | set(new_configs.keys()):
            if old_configs.get(name) != new_configs.get(name):
                stats["configs_changed"] += 1
        
        # Check settings
        if old_state.get('config') != new_state.get('config'):
            stats["settings_changed"] = 1
        
        return stats
    
    def commit(self, message: str, description: str = "", 
               author: str = "admin", tags: List[str] = None) -> Tuple[bool, str, Optional[Commit]]:
        """
        Create a new commit (like git commit)
        
        Args:
            message: Short commit message (like git -m)
            description: Detailed description
            author: Commit author
            tags: Tags for categorization (e.g., ["production", "ssl-update"])
        
        Returns:
            (success, message, commit_object)
        """
        try:
            # Capture current state
            current_state = self._capture_current_state()
            state_json = json.dumps(current_state, sort_keys=True)
            commit_hash = self._generate_hash(state_json + str(datetime.now()))
            
            # Get parent commit
            commits = self._load_commits()
            parent_hash = commits[-1].hash if commits else None
            parent_state = commits[-1].domains_snapshot if commits else {"domains": [], "nginx_configs": {}}
            
            # Calculate diff
            files_changed = list(current_state.get("nginx_configs", {}).keys())
            stats = self._calculate_diff(parent_state, current_state)
            
            # Create commit object
            commit = Commit(
                hash=commit_hash,
                timestamp=datetime.now().isoformat(),
                author=author,
                message=message,
                description=description,
                tags=tags or [],
                parent=parent_hash,
                files_changed=files_changed,
                domains_snapshot=current_state,
                config_snapshot=self.manager.config.copy(),
                stats=stats
            )
            
            # Save commit object
            commit_file = self.commits_dir / f"{commit_hash}.json"
            with open(commit_file, 'w') as f:
                json.dump(commit.to_dict(), f, indent=2)
            
            # Create tarball backup
            backup_file = self.objects_dir / f"{commit_hash}.tar.gz"
            self._create_backup_archive(backup_file, current_state)
            
            # Update commits list
            commits.append(commit)
            self._save_commits(commits)
            
            # Update current branch
            branches = self._load_branches()
            current_branch_name = self._get_current_branch()
            for branch in branches:
                if branch.name == current_branch_name:
                    branch.current_commit = commit_hash
                    break
            self._save_branches(branches)
            
            logger.info(f"Created commit {commit.short_hash()}: {message}")
            return True, f"Commit created: {commit.short_hash()}", commit
        
        except Exception as e:
            logger.error(f"Failed to create commit: {e}")
            return False, f"Failed to create commit: {e}", None
    
    def _create_backup_archive(self, archive_path: Path, state: Dict):
        """Create backup archive"""
        import tempfile
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Save domains
            with open(temp_path / "domains.json", 'w') as f:
                json.dump(state["domains"], f, indent=2)
            
            # Save config
            with open(temp_path / "config.json", 'w') as f:
                json.dump(state["config"], f, indent=2)
            
            # Save NGINX configs
            nginx_dir = temp_path / "nginx"
            nginx_dir.mkdir()
            for name, content in state.get("nginx_configs", {}).items():
                with open(nginx_dir / f"{name}.conf", 'w') as f:
                    f.write(content)
            
            # Create archive
            with tarfile.open(archive_path, 'w:gz') as tar:
                tar.add(temp_path, arcname='backup')
    
    def log(self, limit: int = 10, branch: str = None) -> List[Commit]:
        """
        Get commit history (like git log)
        
        Args:
            limit: Maximum number of commits to return
            branch: Specific branch (None for current)
        
        Returns:
            List of commits
        """
        commits = self._load_commits()
        
        if branch:
            branches = self._load_branches()
            target_branch = None
            for b in branches:
                if b.name == branch:
                    target_branch = b
                    break
            
            if target_branch and target_branch.current_commit:
                # Filter commits up to branch head
                filtered = []
                current_hash = target_branch.current_commit
                for commit in reversed(commits):
                    filtered.append(commit)
                    if commit.hash == current_hash:
                        break
                commits = list(reversed(filtered))
        
        return commits[-limit:] if limit else commits
    
    def show(self, commit_hash: str) -> Tuple[bool, Optional[Commit], Optional[str]]:
        """
        Show commit details (like git show)
        
        Returns:
            (success, commit, diff_text)
        """
        commits = self._load_commits()
        
        # Find commit
        commit = None
        for c in commits:
            if c.hash.startswith(commit_hash) or c.hash == commit_hash:
                commit = c
                break
        
        if not commit:
            return False, None, "Commit not found"
        
        # Generate diff
        diff_text = self._generate_diff_text(commit)
        
        return True, commit, diff_text
    
    def _generate_diff_text(self, commit: Commit) -> str:
        """Generate human-readable diff text"""
        lines = []
        
        lines.append(f"commit {commit.hash}")
        lines.append(f"Author: {commit.author}")
        lines.append(f"Date: {commit.timestamp}")
        lines.append("")
        lines.append(f"    {commit.message}")
        if commit.description:
            lines.append(f"    {commit.description}")
        lines.append("")
        
        # Stats
        stats = commit.stats
        lines.append(f"Stats:")
        lines.append(f"  Domains added: {stats.get('domains_added', 0)}")
        lines.append(f"  Domains removed: {stats.get('domains_removed', 0)}")
        lines.append(f"  Domains modified: {stats.get('domains_modified', 0)}")
        lines.append(f"  Configs changed: {stats.get('configs_changed', 0)}")
        lines.append("")
        
        # Files changed
        if commit.files_changed:
            lines.append(f"Files changed ({len(commit.files_changed)}):")
            for file in commit.files_changed:
                lines.append(f"  - {file}")
        
        return "\n".join(lines)
    
    def checkout(self, commit_hash: str) -> Tuple[bool, str]:
        """
        Checkout a specific commit (restore configuration)
        
        Args:
            commit_hash: Commit hash or short hash
        
        Returns:
            (success, message)
        """
        commits = self._load_commits()
        
        # Find commit
        commit = None
        for c in commits:
            if c.hash.startswith(commit_hash) or c.hash == commit_hash:
                commit = c
                break
        
        if not commit:
            return False, "Commit not found"
        
        try:
            # Create safety backup before checkout
            self.commit(
                f"Auto-backup before checkout to {commit.short_hash()}",
                "Automatic safety backup",
                tags=["auto-backup", "pre-checkout"]
            )
            
            # Restore state
            state = commit.domains_snapshot
            
            # Restore domains
            from .core import Domain
            self.manager.domains = [Domain.from_dict(d) for d in state["domains"]]
            self.manager.save_domains()
            
            # Restore config
            self.manager.config = state["config"].copy()
            self.manager.save_config()
            
            # Restore NGINX configs
            for name, content in state.get("nginx_configs", {}).items():
                config_file = NGINX_SITES_DIR / name
                with open(config_file, 'w') as f:
                    f.write(content)
                
                # Enable site
                self.manager.enable_site(name)
            
            # Test and reload NGINX
            success, msg = self.manager.test_and_reload_nginx()
            if not success:
                return False, f"NGINX configuration test failed: {msg}"
            
            logger.info(f"Checked out commit {commit.short_hash()}")
            return True, f"Successfully restored to commit {commit.short_hash()}"
        
        except Exception as e:
            logger.error(f"Failed to checkout commit: {e}")
            return False, f"Failed to checkout commit: {e}"
    
    def branch(self, action: str, name: str = None, description: str = "") -> Tuple[bool, str, Optional[List[Branch]]]:
        """
        Manage branches (like git branch)
        
        Args:
            action: "list", "create", "delete", "switch"
            name: Branch name (for create/delete/switch)
            description: Branch description (for create)
        
        Returns:
            (success, message, branches_list)
        """
        branches = self._load_branches()
        current_branch = self._get_current_branch()
        
        if action == "list":
            return True, "Branches listed", branches
        
        elif action == "create":
            if not name:
                return False, "Branch name required", None
            
            # Check if branch exists
            if any(b.name == name for b in branches):
                return False, f"Branch '{name}' already exists", None
            
            # Get current commit
            commits = self._load_commits()
            current_commit = commits[-1].hash if commits else ""
            
            # Create new branch
            new_branch = Branch(
                name=name,
                current_commit=current_commit,
                created_at=datetime.now().isoformat(),
                description=description
            )
            
            branches.append(new_branch)
            self._save_branches(branches)
            
            return True, f"Branch '{name}' created", branches
        
        elif action == "delete":
            if not name:
                return False, "Branch name required", None
            
            if name == "main":
                return False, "Cannot delete main branch", None
            
            if name == current_branch:
                return False, "Cannot delete current branch", None
            
            branches = [b for b in branches if b.name != name]
            self._save_branches(branches)
            
            return True, f"Branch '{name}' deleted", branches
        
        elif action == "switch":
            if not name:
                return False, "Branch name required", None
            
            # Check if branch exists
            target_branch = None
            for b in branches:
                if b.name == name:
                    target_branch = b
                    break
            
            if not target_branch:
                return False, f"Branch '{name}' not found", None
            
            # Switch branch
            self._set_current_branch(name)
            
            # Checkout branch head if it exists
            if target_branch.current_commit:
                success, msg = self.checkout(target_branch.current_commit)
                if not success:
                    return False, f"Failed to checkout branch: {msg}", None
            
            return True, f"Switched to branch '{name}'", branches
        
        else:
            return False, f"Unknown action: {action}", None
    
    def tag(self, commit_hash: str, tag_name: str, message: str = "") -> Tuple[bool, str]:
        """
        Tag a commit (like git tag)
        
        Args:
            commit_hash: Commit to tag
            tag_name: Tag name (e.g., "v1.0", "production-2025-12-11")
            message: Tag message
        
        Returns:
            (success, message)
        """
        commits = self._load_commits()
        
        # Find commit
        commit = None
        for c in commits:
            if c.hash.startswith(commit_hash) or c.hash == commit_hash:
                commit = c
                break
        
        if not commit:
            return False, "Commit not found"
        
        # Update commit tags
        if tag_name not in commit.tags:
            commit.tags.append(tag_name)
        
        # Save updated commits
        self._save_commits(commits)
        
        # Create tag file
        tag_file = self.tags_dir / f"{tag_name}.json"
        tag_data = {
            "name": tag_name,
            "commit": commit.hash,
            "message": message,
            "created_at": datetime.now().isoformat()
        }
        with open(tag_file, 'w') as f:
            json.dump(tag_data, f, indent=2)
        
        logger.info(f"Tagged commit {commit.short_hash()} as '{tag_name}'")
        return True, f"Created tag '{tag_name}' at {commit.short_hash()}"
    
    def diff(self, commit1: str, commit2: str = None) -> Tuple[bool, str]:
        """
        Show differences between commits (like git diff)
        
        Args:
            commit1: First commit hash
            commit2: Second commit hash (None for current state)
        
        Returns:
            (success, diff_text)
        """
        commits = self._load_commits()
        
        # Find first commit
        c1 = None
        for c in commits:
            if c.hash.startswith(commit1) or c.hash == commit1:
                c1 = c
                break
        
        if not c1:
            return False, "First commit not found"
        
        # Get states to compare
        state1 = c1.domains_snapshot
        
        if commit2:
            c2 = None
            for c in commits:
                if c.hash.startswith(commit2) or c.hash == commit2:
                    c2 = c
                    break
            
            if not c2:
                return False, "Second commit not found"
            
            state2 = c2.domains_snapshot
            header = f"diff {c1.short_hash()}..{c2.short_hash()}"
        else:
            state2 = self._capture_current_state()
            header = f"diff {c1.short_hash()}..working"
        
        # Generate diff
        diff_lines = [header, ""]
        
        # Compare domains
        domains1 = {d['name']: d for d in state1.get('domains', [])}
        domains2 = {d['name']: d for d in state2.get('domains', [])}
        
        all_domains = set(domains1.keys()) | set(domains2.keys())
        
        for domain_name in sorted(all_domains):
            d1 = domains1.get(domain_name)
            d2 = domains2.get(domain_name)
            
            if d1 and not d2:
                diff_lines.append(f"--- Domain removed: {domain_name}")
                diff_lines.append(f"    Port: {d1['port']}, SSL: {d1['ssl']}")
            elif not d1 and d2:
                diff_lines.append(f"+++ Domain added: {domain_name}")
                diff_lines.append(f"    Port: {d2['port']}, SSL: {d2['ssl']}")
            elif d1 != d2:
                diff_lines.append(f"~~~ Domain modified: {domain_name}")
                if d1['port'] != d2['port']:
                    diff_lines.append(f"    Port: {d1['port']} -> {d2['port']}")
                if d1['ssl'] != d2['ssl']:
                    diff_lines.append(f"    SSL: {d1['ssl']} -> {d2['ssl']}")
        
        # Compare NGINX configs
        configs1 = state1.get('nginx_configs', {})
        configs2 = state2.get('nginx_configs', {})
        
        all_configs = set(configs1.keys()) | set(configs2.keys())
        
        for config_name in sorted(all_configs):
            c1_content = configs1.get(config_name, "").split('\n')
            c2_content = configs2.get(config_name, "").split('\n')
            
            if c1_content != c2_content:
                diff_lines.append(f"\nConfig: {config_name}")
                config_diff = list(difflib.unified_diff(
                    c1_content, c2_content,
                    lineterm='',
                    fromfile=f"{config_name} ({c1.short_hash() if commit2 else 'old'})",
                    tofile=f"{config_name} ({'working' if not commit2 else c2.short_hash()})"
                ))
                diff_lines.extend(config_diff[:50])  # Limit to 50 lines
        
        return True, "\n".join(diff_lines)
    
    def status(self) -> Tuple[bool, Dict]:
        """
        Show current status (like git status)
        
        Returns:
            (success, status_dict)
        """
        try:
            current_branch = self._get_current_branch()
            commits = self._load_commits()
            last_commit = commits[-1] if commits else None
            
            # Check for uncommitted changes
            current_state = self._capture_current_state()
            
            has_changes = False
            if last_commit:
                stats = self._calculate_diff(last_commit.domains_snapshot, current_state)
                has_changes = any(stats.values())
            else:
                has_changes = bool(current_state["domains"])
            
            status = {
                "branch": current_branch,
                "last_commit": last_commit.short_hash() if last_commit else None,
                "last_commit_message": last_commit.message if last_commit else None,
                "last_commit_time": last_commit.timestamp if last_commit else None,
                "has_uncommitted_changes": has_changes,
                "total_commits": len(commits),
                "domains_count": len(self.manager.domains)
            }
            
            return True, status
        
        except Exception as e:
            logger.error(f"Failed to get status: {e}")
            return False, {}
    
    def get_stats(self) -> Dict:
        """Get repository statistics"""
        commits = self._load_commits()
        branches = self._load_branches()
        
        # Calculate stats
        total_domains_added = sum(c.stats.get('domains_added', 0) for c in commits)
        total_domains_removed = sum(c.stats.get('domains_removed', 0) for c in commits)
        
        authors = {}
        for commit in commits:
            authors[commit.author] = authors.get(commit.author, 0) + 1
        
        tags = set()
        for commit in commits:
            tags.update(commit.tags)
        
        return {
            "total_commits": len(commits),
            "total_branches": len(branches),
            "total_tags": len(tags),
            "total_domains_added": total_domains_added,
            "total_domains_removed": total_domains_removed,
            "authors": authors,
            "repository_size": self._calculate_repo_size()
        }
    
    def _calculate_repo_size(self) -> str:
        """Calculate repository size"""
        total_size = 0
        for path in self.vcs_dir.rglob('*'):
            if path.is_file():
                total_size += path.stat().st_size
        
        # Convert to human readable
        for unit in ['B', 'KB', 'MB', 'GB']:
            if total_size < 1024:
                return f"{total_size:.2f} {unit}"
            total_size /= 1024
        
        return f"{total_size:.2f} TB"
