from dealeriq_api.auth.passwords import hash_password, verify_password


def test_hash_is_not_the_plaintext() -> None:
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert hashed.startswith("$argon2id$")


def test_verify_accepts_the_correct_password() -> None:
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed) is True


def test_verify_rejects_a_wrong_password() -> None:
    hashed = hash_password("correct horse battery staple")
    assert verify_password("wrong password", hashed) is False


def test_argon2id_parameters_meet_srs_minimums() -> None:
    # FR-002: memory >= 64 MiB, iterations >= 3. Parse them back out of the encoded hash
    # rather than trusting our own constant, so this test would fail if ADR-009's constants
    # were ever accidentally weakened.
    hashed = hash_password("anything")
    # format: $argon2id$v=19$m=65536,t=3,p=4$salt$hash
    params_segment = hashed.split("$")[3]
    params = dict(part.split("=") for part in params_segment.split(","))
    assert int(params["m"]) >= 65536  # KiB, i.e. 64 MiB
    assert int(params["t"]) >= 3
