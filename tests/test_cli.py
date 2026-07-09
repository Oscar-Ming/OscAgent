from oscagent.cli import build_parser


def test_cli_has_doctor_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["doctor"])

    assert args.command == "doctor"
    assert callable(args.func)


def test_cli_has_discord_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["discord"])

    assert args.command == "discord"
    assert callable(args.func)
