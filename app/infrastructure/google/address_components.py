from collections.abc import Iterable

Component = tuple[str | None, str | None]  # (nome longo, nome curto)


def index_by_type(components: Iterable[tuple[Iterable[str], Component]]) -> dict[str, Component]:
    """Indexa os componentes por tipo, mantendo o primeiro de cada tipo"""
    by_type: dict[str, Component] = {}
    for types, component in components:
        for component_type in types:
            by_type.setdefault(component_type, component)
    return by_type


def address_fields(by_type: dict[str, Component]) -> dict[str, str | None]:
    """Traduz os componentes indexados por tipo para os campos estruturados de `Address` (Brasil)"""

    def long(*types: str) -> str | None:
        return next((by_type[t][0] for t in types if t in by_type and by_type[t][0]), None)

    def short(component_type: str) -> str | None:
        component = by_type.get(component_type)
        return component[1] if component else None

    return {
        "street_name": long("route"),
        "street_number": long("street_number"),
        "complement": long("subpremise"),
        "neighborhood": long("sublocality_level_1", "sublocality", "neighborhood"),
        "city": long("locality", "administrative_area_level_2"),
        "state": short("administrative_area_level_1"),
        "postal_code": long("postal_code"),
        "country_code": short("country"),
    }
