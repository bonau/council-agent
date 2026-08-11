"""Unit tests for Council principals and the canonical scope matrix."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from council_agent.llm.openrouter import (
    OpenRouterCredential,
    make_llm,
)
from council_agent.security import (
    ALL_PRINCIPAL_SCOPES,
    AuthorizationReason,
    Principal,
    PrincipalKind,
    PrincipalScope,
    evaluate_principal_scopes,
    full_scope_principal,
    local_cli_principal,
    parse_principal_scopes,
    required_scopes_for_action,
)


def _principal(
    *scopes: PrincipalScope,
    principal_id: str = "local:user@example.test",
) -> Principal:
    return Principal(
        principal_id=principal_id,
        kind=PrincipalKind.LOCAL_USER,
        issuer="test-suite",
        scopes=frozenset(scopes),
    )


def test_principal_is_immutable_and_has_stable_masked_reference() -> None:
    principal = _principal(PrincipalScope.READ)
    same_identity = _principal(
        PrincipalScope.READ,
        PrincipalScope.FILESYSTEM_MUTATE,
    )

    assert principal.audit_ref == same_identity.audit_ref
    assert principal.principal_id not in principal.audit_ref
    assert principal.audit_ref.startswith("sha256:")
    with pytest.raises(FrozenInstanceError):
        principal.principal_id = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    "kwargs",
    [
        {
            "principal_id": "",
            "kind": PrincipalKind.LOCAL_USER,
            "issuer": "issuer",
            "scopes": frozenset(),
        },
        {
            "principal_id": "id",
            "kind": "unknown",
            "issuer": "issuer",
            "scopes": frozenset(),
        },
        {
            "principal_id": "id",
            "kind": PrincipalKind.LOCAL_USER,
            "issuer": "",
            "scopes": frozenset(),
        },
        {
            "principal_id": "id",
            "kind": PrincipalKind.LOCAL_USER,
            "issuer": "issuer",
            "scopes": frozenset({"read"}),
        },
        {
            "principal_id": "id",
            "kind": PrincipalKind.LOCAL_USER,
            "issuer": "issuer",
            "scopes": {PrincipalScope.READ},
        },
    ],
)
def test_principal_rejects_invalid_identity_and_scopes(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        Principal(**kwargs)


def test_scope_parser_is_strict_and_deduplicates() -> None:
    scopes = parse_principal_scopes("read, test,read, filesystem:mutate")

    assert scopes == frozenset(
        {
            PrincipalScope.READ,
            PrincipalScope.TEST,
            PrincipalScope.FILESYSTEM_MUTATE,
        }
    )
    with pytest.raises(ValueError, match="Unknown Council principal scope"):
        parse_principal_scopes("read,filesystem:write")


def test_full_scope_principal_contains_closed_scope_set() -> None:
    principal = full_scope_principal("pytest")

    assert principal.scopes == ALL_PRINCIPAL_SCOPES
    assert {scope.value for scope in principal.scopes} == {
        "read",
        "filesystem:mutate",
        "test",
        "shell",
        "high-risk:manage",
    }


def test_provider_credential_masks_secret_and_is_not_a_principal() -> None:
    secret = "sk-or-v1-provider-secret"
    credential = OpenRouterCredential(secret)

    assert credential.get_secret_value() == secret
    assert secret not in repr(credential)
    with pytest.raises(ValueError, match="principal_id"):
        Principal(
            principal_id=credential,  # type: ignore[arg-type]
            kind=PrincipalKind.SERVICE,
            issuer="provider",
            scopes=frozenset(),
        )


def test_openrouter_factory_reveals_key_only_to_model_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []

    class FakeLLM:
        def __init__(self, **kwargs: object) -> None:
            calls.append(kwargs)

    monkeypatch.setattr("council_agent.llm.openrouter.LLM", FakeLLM)
    credential = OpenRouterCredential("provider-secret")

    make_llm("model", 0.25, credential)

    assert calls == [
        {
            "model": "openrouter/model",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key": "provider-secret",
            "temperature": 0.25,
        }
    ]
    with pytest.raises(TypeError, match="OpenRouterCredential"):
        make_llm(
            "model",
            0.25,
            _principal(PrincipalScope.READ),  # type: ignore[arg-type]
        )


def test_local_cli_principal_defaults_full_and_parses_narrow_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("getpass.getuser", lambda: "stable-user")

    default = local_cli_principal()
    narrowed = local_cli_principal("configured-id", "read")

    assert default.principal_id == "local-user:stable-user"
    assert default.scopes == ALL_PRINCIPAL_SCOPES
    assert narrowed.principal_id == "configured-id"
    assert narrowed.scopes == frozenset({PrincipalScope.READ})


@pytest.mark.parametrize(
    ("tool_name", "tool_args", "expected"),
    [
        ("read_file", {"path": "a"}, {PrincipalScope.READ}),
        ("list_dir", {"path": "."}, {PrincipalScope.READ}),
        (
            "write_file",
            {"path": "a", "content": "x"},
            {PrincipalScope.FILESYSTEM_MUTATE},
        ),
        (
            "delete_file",
            {"path": "a"},
            {PrincipalScope.FILESYSTEM_MUTATE},
        ),
        (
            "run_tests",
            {"path": "."},
            {PrincipalScope.TEST, PrincipalScope.FILESYSTEM_MUTATE},
        ),
        (
            "run_command",
            {"command": "cat README.md"},
            {PrincipalScope.SHELL, PrincipalScope.READ},
        ),
        (
            "run_command",
            {"command": "mkdir build"},
            {PrincipalScope.SHELL, PrincipalScope.FILESYSTEM_MUTATE},
        ),
        (
            "run_command",
            {"command": "rm -rf build"},
            {
                PrincipalScope.SHELL,
                PrincipalScope.FILESYSTEM_MUTATE,
                PrincipalScope.HIGH_RISK_MANAGE,
            },
        ),
    ],
)
def test_required_scopes_cover_every_action_matrix_row(
    tool_name: str,
    tool_args: dict,
    expected: set[PrincipalScope],
) -> None:
    assert required_scopes_for_action(tool_name, tool_args) == frozenset(expected)


def test_rejected_shell_input_still_requires_shell_scope() -> None:
    assert required_scopes_for_action(
        "run_command",
        {"command": "unknown-command"},
    ) == frozenset({PrincipalScope.SHELL})


def test_unknown_product_tool_has_no_scope_fallback() -> None:
    with pytest.raises(ValueError, match="Unknown product tool"):
        required_scopes_for_action("not_registered", {})


def test_scope_decision_reports_missing_authority_without_raw_identity() -> None:
    principal = _principal(PrincipalScope.READ)
    required = frozenset(
        {PrincipalScope.TEST, PrincipalScope.FILESYSTEM_MUTATE}
    )

    decision = evaluate_principal_scopes(principal, principal, required)
    metadata = decision.to_metadata()

    assert decision.allowed is False
    assert decision.reason is AuthorizationReason.SCOPE_INSUFFICIENT
    assert decision.missing_scopes == required
    assert metadata["principal_ref"] == principal.audit_ref
    assert principal.principal_id not in str(metadata)


def test_scope_decision_distinguishes_missing_revoked_invalid_and_mismatch() -> None:
    expected = _principal(PrincipalScope.READ)
    required = frozenset({PrincipalScope.READ})
    replacement = _principal(
        PrincipalScope.READ,
        principal_id="other",
    )

    assert (
        evaluate_principal_scopes(None, None, required).reason
        is AuthorizationReason.PRINCIPAL_MISSING
    )
    assert (
        evaluate_principal_scopes(expected, None, required).reason
        is AuthorizationReason.PRINCIPAL_REVOKED
    )
    assert (
        evaluate_principal_scopes(expected, object(), required).reason
        is AuthorizationReason.PRINCIPAL_INVALID
    )
    assert (
        evaluate_principal_scopes(expected, replacement, required).reason
        is AuthorizationReason.PRINCIPAL_MISMATCH
    )


def test_scope_decision_allows_complete_current_authority() -> None:
    principal = _principal(
        PrincipalScope.SHELL,
        PrincipalScope.READ,
    )
    required = frozenset({PrincipalScope.SHELL, PrincipalScope.READ})

    decision = evaluate_principal_scopes(principal, principal, required)

    assert decision.allowed is True
    assert decision.reason is AuthorizationReason.ALLOWED
    assert decision.missing_scopes == frozenset()
