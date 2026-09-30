"""Conversion of the object model into plain dictionaries, JSON and a text summary."""

from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any, Dict, List, Union

from .compiler import CompilationResult
from .model import (
    AssociationClass,
    ClassDiagram,
    Entity,
    Member,
    Note,
    NoteLink,
    Package,
    Relationship,
    Separator,
)


def to_dict(obj: Union[CompilationResult, ClassDiagram]) -> Dict[str, Any]:
    """Plain, JSON-compatible dictionary. References between objects become qualified names."""
    if isinstance(obj, CompilationResult):
        return {
            "diagrams": [to_dict(d) for d in obj.diagrams],
            "skipped": [_plain(s) for s in obj.skipped],
            "diagnostics": [_plain(d) for d in obj.diagnostics],
        }
    return _diagram(obj)


def to_json(obj: Union[CompilationResult, ClassDiagram], indent: int = 2) -> str:
    return json.dumps(to_dict(obj), indent=indent, ensure_ascii=False)


def summarize(diagram: ClassDiagram) -> str:
    """Short human readable description of a diagram."""
    lines: List[str] = []
    title = f" '{diagram.title}'" if diagram.title else ""
    lines.append(f"Class diagram{title} (line {diagram.start_line})")
    if diagram.name:
        lines.append(f"  name: {diagram.name}")
    lines.append(f"  packages: {len(diagram.packages)}")
    lines.append(f"  entities: {len(diagram.entities)}")
    for entity in diagram.entities.values():
        extra = " (implicit)" if entity.implicit else ""
        members = f", {len(entity.fields)} field(s), {len(entity.methods)} method(s)" if entity.members else ""
        lines.append(f"    {entity.kind.value} {entity.qualified_name}{extra}{members}")
    lines.append(f"  relationships: {len(diagram.relationships)}")
    for rel in diagram.relationships:
        label = f" : {rel.label}" if rel.label else ""
        lines.append(f"    {_endpoint(rel.source)} -{rel.kind.value}-> {_endpoint(rel.target)}{label}")
    if diagram.notes:
        lines.append(f"  notes: {len(diagram.notes)}")
    if diagram.association_classes:
        lines.append(f"  association classes: {len(diagram.association_classes)}")
    if diagram.rules:
        lines.append(f"  hide/show rules: {len(diagram.rules)}")
    if diagram.diagnostics:
        lines.append(f"  diagnostics: {len(diagram.diagnostics)}")
        for d in diagram.diagnostics:
            lines.append(f"    {d}")
    return "\n".join(lines)


# ---------------------------------------------------------------------- internals


def _endpoint(obj: Union[Entity, Package]) -> str:
    return obj.qualified_name


def _plain(obj: Any) -> Any:
    """Generic conversion for simple dataclasses without object references."""
    if isinstance(obj, Enum):
        return obj.value
    if is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _plain(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, (list, tuple)):
        return [_plain(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _plain(v) for k, v in obj.items()}
    return obj


def _diagram(d: ClassDiagram) -> Dict[str, Any]:
    data = {
        f.name: _plain(getattr(d, f.name))
        for f in fields(d)
        if f.name
        not in ("root", "entities", "packages", "relationships", "notes", "note_links", "association_classes", "rules")
    }
    data["root"] = _package(d.root)
    data["entities"] = [_entity(e) for e in d.entities.values()]
    data["packages"] = [_package(p, children=False) for p in d.packages.values()]
    data["relationships"] = [_relationship(r, d) for r in d.relationships]
    data["notes"] = [_note(n) for n in d.notes]
    data["note_links"] = [_note_link(n) for n in d.note_links]
    data["association_classes"] = [_association_class(a, d) for a in d.association_classes]
    data["rules"] = [_plain(r) for r in d.rules]
    return data


def _entity(e: Entity) -> Dict[str, Any]:
    return {
        "name": e.name,
        "qualified_name": e.qualified_name,
        "kind": e.kind.value,
        "display_name": e.display_name,
        "namespace": e.namespace,
        "package": e.package.qualified_name if e.package and e.package.qualified_name else None,
        "generics": e.generics,
        "stereotypes": list(e.stereotypes),
        "spot": _plain(e.spot),
        "color": e.color,
        "url": e.url,
        "tooltip": e.tooltip,
        "tags": list(e.tags),
        "extends": [x.qualified_name for x in e.extends],
        "implements": [x.qualified_name for x in e.implements],
        "members": [_member(m) for m in e.members],
        "implicit": e.implicit,
        "line": e.line,
    }


def _member(m: Union[Member, Separator]) -> Dict[str, Any]:
    data = _plain(m)
    data["item"] = "member" if isinstance(m, Member) else "separator"
    return data


def _package(p: Package, children: bool = True) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "name": p.name,
        "qualified_name": p.qualified_name,
        "kind": p.kind.value,
        "display_name": p.display_name,
        "stereotypes": list(p.stereotypes),
        "color": p.color,
        "url": p.url,
        "tooltip": p.tooltip,
        "tags": list(p.tags),
        "line": p.line,
    }
    if children:
        data["children"] = [
            {"entity": c.qualified_name} if isinstance(c, Entity) else _package(c) for c in p.children
        ]
    return data


def _relationship(r: Relationship, d: ClassDiagram) -> Dict[str, Any]:
    return {
        "source": r.source.qualified_name,
        "target": r.target.qualified_name,
        "kind": r.kind.value,
        "source_head": r.source_head.name.lower(),
        "target_head": r.target_head.name.lower(),
        "line_style": r.line_style.value,
        "length": r.length,
        "direction": r.direction.value if r.direction else None,
        "bold": r.bold,
        "hidden": r.hidden,
        "color": r.color,
        "text_color": r.text_color,
        "thickness": r.thickness,
        "label": r.label,
        "label_arrow": r.label_arrow,
        "source_cardinality": r.source_cardinality,
        "target_cardinality": r.target_cardinality,
        "source_qualifier": r.source_qualifier,
        "target_qualifier": r.target_qualifier,
        "source_member": r.source_member,
        "target_member": r.target_member,
        "socket": r.socket,
        "norank": r.norank,
        "note": d.notes.index(r.note) if r.note is not None else None,  # index into "notes"
        "from_declaration": r.from_declaration,
        "line": r.line,
    }


def _note(n: Note) -> Dict[str, Any]:
    target = n.target
    if isinstance(target, Relationship):
        target_value: Any = {"relationship": f"{target.source.qualified_name} -> {target.target.qualified_name}"}
    elif target is None:
        target_value = None
    else:
        target_value = target.qualified_name
    return {
        "text": n.text,
        "position": n.position.value if n.position else None,
        "target": target_value,
        "alias": n.alias,
        "member": n.member,
        "color": n.color,
        "line": n.line,
    }


def _note_link(n: NoteLink) -> Dict[str, Any]:
    return {"note": n.note.alias, "target": n.target.qualified_name, "line_style": n.line_style.value, "line": n.line}


def _association_class(a: AssociationClass, d: ClassDiagram) -> Dict[str, Any]:
    return {
        "first": a.first.qualified_name,
        "second": a.second.qualified_name,
        "entity": a.entity.qualified_name,
        "relationship": d.relationships.index(a.relationship) if a.relationship is not None else None,
        "line_style": a.line_style.value,
        "line": a.line,
    }
