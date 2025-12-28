import click
from flask import Flask
from sqlalchemy import func

from .extensions import db


def register_cli_commands(app: Flask) -> None:
    @app.cli.command("create-admin")
    @click.argument("email")
    def create_admin(email: str) -> None:
        """Create an admin user placeholder."""
        from .models import User

        user = User.query.filter_by(email=email).first()
        if user:
            click.echo("User already exists")
            return
        user = User(
            first_name="Admin",
            last_name="User",
            email=email,
            is_active=True,
        )
        user.set_password("ChangeMe123!")
        db.session.add(user)
        db.session.commit()
        click.echo("Admin user created")

    @app.cli.command("seed-demo-data")
    def seed_demo_data() -> None:
        """Populate the database with demo users, tournaments, and participants."""
        from datetime import datetime, timedelta

        from .models import User, Tournament, TournamentParticipant

        now = datetime.utcnow()

        # Create a few users, including mastrm.enterprise as demo organizer
        users: list[User] = []
        demo_specs = [
            ("Mario", "Rossi", "mario@example.com"),
            ("Luigi", "Verdi", "luigi@example.com"),
            ("Anna", "Bianchi", "anna@example.com"),
            ("Mastrm", "Enterprise", "mastrm.enterprise@gmail.com"),
        ]
        for first_name, last_name, email in demo_specs:
            user = User.query.filter_by(email=email).first()
            if not user:
                user = User(
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    is_active=True,
                )
                user.set_password("Password123!")
                db.session.add(user)
                users.append(user)

        db.session.commit()

        if not users:
            users = User.query.filter(User.email.in_([e for _, _, e in demo_specs])).all()

        if not users:
            click.echo("No users available to create tournaments.")
            return

        # Use mastrm.enterprise as the organizer for demo tournaments
        organizer = User.query.filter_by(email="mastrm.enterprise@gmail.com").first()
        if not organizer:
            click.echo("Organizer mastrm.enterprise@gmail.com not found, aborting.")
            return

        t1 = Tournament.query.filter_by(
            organizer_id=organizer.id, name="Demo Tennis Open"
        ).first()
        if not t1:
            t1 = Tournament(
                organizer_id=organizer.id,
                name="Demo Tennis Open",
                discipline="tennis",
                description="Demo tennis tournament.",
                venue_name="Centro Sportivo Demo",
                start_at=now + timedelta(days=3),
                signup_deadline=now + timedelta(days=2),
                max_participants=8,
                status="draft",
            )
            db.session.add(t1)

        t2 = Tournament.query.filter_by(
            organizer_id=organizer.id, name="Demo Chess Cup"
        ).first()
        if not t2:
            t2 = Tournament(
                organizer_id=organizer.id,
                name="Demo Chess Cup",
                discipline="chess",
                description="Demo chess tournament.",
                venue_name="Circolo Scacchi Demo",
                start_at=now + timedelta(days=5),
                signup_deadline=now + timedelta(days=4),
                max_participants=16,
                status="draft",
            )
            db.session.add(t2)

        db.session.commit()
        click.echo(f"Demo tournaments ready: {t1.name} (id={t1.id}), {t2.name} (id={t2.id})")

        # Create some demo participants for these tournaments
        # Avoid duplicating if participants already exist
        existing_participants_t1 = TournamentParticipant.query.filter_by(
            tournament_id=t1.id
        ).count()
        existing_participants_t2 = TournamentParticipant.query.filter_by(
            tournament_id=t2.id
        ).count()

        if existing_participants_t1 == 0:
            # Up to 8 participants for t1 (respecting max_participants)
            specs_t1 = [
                ("LIC-T1-001", 1),
                ("LIC-T1-002", 2),
                ("LIC-T1-003", 3),
                ("LIC-T1-004", 4),
                ("LIC-T1-005", 5),
                ("LIC-T1-006", 6),
                ("LIC-T1-007", 7),
                ("LIC-T1-008", 8),
            ][: t1.max_participants]

            for idx, (license_number, ranking) in enumerate(specs_t1):
                user = users[idx % len(users)]
                p = TournamentParticipant(
                    tournament_id=t1.id,
                    user_id=user.id,
                    license_number=license_number,
                    ranking=ranking,
                    status="pending",
                )
                db.session.add(p)

            click.echo(f"Created {len(specs_t1)} participants for {t1.name}.")

        if existing_participants_t2 == 0:
            # Up to 16 participants for t2 (respecting max_participants)
            specs_t2 = [
                (f"LIC-T2-{i:03d}", i) for i in range(1, min(t2.max_participants, 16) + 1)
            ]

            for idx, (license_number, ranking) in enumerate(specs_t2):
                user = users[idx % len(users)]
                p = TournamentParticipant(
                    tournament_id=t2.id,
                    user_id=user.id,
                    license_number=license_number,
                    ranking=ranking,
                    status="pending",
                )
                db.session.add(p)

            click.echo(f"Created {len(specs_t2)} participants for {t2.name}.")

        db.session.commit()

        total_participants = TournamentParticipant.query.count()
        click.echo(
            f"Seed complete. Users: {User.query.count()}, Tournaments: {Tournament.query.count()}, Participants: {total_participants}."
        )

    @app.cli.command("seed-bracket-example")
    def seed_bracket_example() -> None:
        """Create a specific tournament + bracket scenario to test the tree.

        This command creates:
        - An organizer user "MARIO Mastrulli" (if not present)
        - A tournament named "prova definitiva albero" with the dates you provided
        - 10 participants with rankings 111–120 and the given license numbers
        - Round 1 matches and example winners for matches 1–5

        After running it, open the tournament detail page in the browser
        to visually inspect the bracket.
        """

        from datetime import datetime

        from .models import User, Tournament, TournamentParticipant, Match
        from .tournaments.routes import _ensure_round1_bracket, _advance_winner

        # 1) Ensure organizer exists
        organizer_email = "mario.mastrulli@example.com"
        organizer = User.query.filter_by(email=organizer_email).first()
        if not organizer:
            organizer = User(
                first_name="MARIO",
                last_name="Mastrulli",
                email=organizer_email,
                is_active=True,
            )
            organizer.set_password("Password123!")
            db.session.add(organizer)
            db.session.commit()
            click.echo(f"Created organizer user {organizer_email} (id={organizer.id}).")

        # 2) Create or reuse the specific tournament
        tournament_name = "prova definitiva albero"
        tournament = Tournament.query.filter_by(
            organizer_id=organizer.id, name=tournament_name
        ).first()

        if not tournament:
            tournament = Tournament(
                organizer_id=organizer.id,
                name=tournament_name,
                discipline="tennis",
                description="Torneo di test per verificare l'albero eliminazione diretta.",
                venue_name="afsaasfsf",
                start_at=datetime(2025, 12, 30, 10, 10, 0),
                signup_deadline=datetime(2025, 12, 29, 10, 10, 0),
                max_participants=10,
                status="draft",
            )
            db.session.add(tournament)
            db.session.commit()
            click.echo(f"Created tournament '{tournament.name}' (id={tournament.id}).")
        else:
            click.echo(f"Using existing tournament '{tournament.name}' (id={tournament.id}).")

        # 3) Clear existing participants & matches for a clean scenario
        Match.query.filter_by(tournament_id=tournament.id).delete()
        TournamentParticipant.query.filter_by(tournament_id=tournament.id).delete()
        db.session.commit()

        # 4) Create the 10 specific participants (ranking & license number)
        participants_spec = [
            (111, "111"),
            (112, "LIC-T007-112"),
            (113, "LIC-T007-113"),
            (114, "LIC-T007-114"),
            (115, "LIC-T007-115"),
            (116, "LIC-T007-116"),
            (117, "LIC-T007-117"),
            (118, "LIC-T007-118"),
            (119, "LIC-T007-119"),
            (120, "LIC-T007-120"),
        ]

        created_participants: list[TournamentParticipant] = []

        for ranking, license_number in participants_spec:
            # Create (or reuse) a simple user for each ranking
            email = f"player_{ranking}@example.com"
            user = User.query.filter_by(email=email).first()
            if not user:
                user = User(
                    first_name=f"Player{ranking}",
                    last_name="Test",
                    email=email,
                    is_active=True,
                )
                user.set_password("Password123!")
                db.session.add(user)
                db.session.flush()

            participant = TournamentParticipant(
                tournament_id=tournament.id,
                user_id=user.id,
                license_number=license_number,
                ranking=ranking,
                status="pending",
            )
            db.session.add(participant)
            created_participants.append(participant)

        db.session.commit()
        click.echo(
            f"Created {len(created_participants)} participants for '{tournament.name}' (id={tournament.id})."
        )

        # 5) Generate Round 1 bracket ignoring the signup deadline
        created_round1 = _ensure_round1_bracket(tournament.id, ignore_deadline=True)
        db.session.commit()

        if not created_round1:
            click.echo("Round 1 bracket was not created (maybe already present).")
        else:
            click.echo("Round 1 bracket created.")

        # 6) Pick winners for matches 1–5 and advance them to Round 2
        round1_matches = (
            Match.query.filter_by(tournament_id=tournament.id, round_number=1)
            .order_by(Match.bracket_position.asc())
            .all()
        )

        winners_info: list[tuple[int, str]] = []

        # Example: for Match 1–5, let player A win (if both players exist)
        for match in round1_matches[:5]:
            if not match.player_a_id or not match.player_b_id:
                # Skip bye / incomplete pairings
                continue

            match.winner_id = match.player_a_id
            _advance_winner(match)

            if match.player_a is not None:
                winners_info.append(
                    (match.bracket_position, match.player_a.license_number)
                )

        db.session.commit()

        if winners_info:
            click.echo("Round 1 example results:")
            for pos, lic in winners_info:
                click.echo(f"  Match {pos}: winner {lic}")
        else:
            click.echo("No winners were assigned in Round 1 (check participants/matches).")

        # 7) Auto-play later rounds until a single champion exists.
        max_iterations = 10
        champion_reported = False

        for _ in range(max_iterations):
            max_round = (
                db.session.query(func.max(Match.round_number))
                .filter_by(tournament_id=tournament.id)
                .scalar()
            )
            if not max_round:
                break

            latest_matches = (
                Match.query.filter_by(
                    tournament_id=tournament.id, round_number=max_round
                )
                .order_by(Match.bracket_position.asc())
                .all()
            )
            if not latest_matches:
                break

            # If there's a single match in the latest round, treat it as final
            # and set the winner without advancing further.
            if len(latest_matches) == 1:
                final_match = latest_matches[0]
                if final_match.winner_id is None:
                    if final_match.player_a_id and final_match.player_b_id:
                        final_match.winner_id = final_match.player_a_id
                    elif final_match.player_a_id and not final_match.player_b_id:
                        final_match.winner_id = final_match.player_a_id
                    elif final_match.player_b_id and not final_match.player_a_id:
                        final_match.winner_id = final_match.player_b_id
                    db.session.commit()

                if final_match.winner is not None:
                    click.echo(
                        "Champion: "
                        f"#{final_match.winner.ranking} ({final_match.winner.license_number})"
                    )
                    champion_reported = True
                break

            progressed_any = False
            for match in latest_matches:
                if match.winner_id is not None:
                    continue

                # If both players are present, arbitrarily let player A win.
                if match.player_a_id and match.player_b_id:
                    match.winner_id = match.player_a_id
                    _advance_winner(match)
                    progressed_any = True
                # If only one player is present, treat it as a bye win.
                elif match.player_a_id and not match.player_b_id:
                    match.winner_id = match.player_a_id
                    _advance_winner(match)
                    progressed_any = True
                elif match.player_b_id and not match.player_a_id:
                    match.winner_id = match.player_b_id
                    _advance_winner(match)
                    progressed_any = True

            db.session.commit()

            if not progressed_any:
                break

        if not champion_reported:
            click.echo("Bracket progressed, but no single champion could be determined.")

        click.echo(
            "Bracket example ready. Open the tournament detail page for 'prova definitiva albero' to inspect the full tree."
        )

    @app.cli.command("seed-tournament-participants")
    @click.argument("tournament_name")
    @click.argument("num_participants", type=int)
    def seed_tournament_participants(tournament_name: str, num_participants: int) -> None:
        """Add demo users and participants to a specific tournament.

        Example:
            flask seed-tournament-participants "PROVA DEFINITIVA ALBERO" 8
        """

        from .models import User, Tournament, TournamentParticipant

        tournament = Tournament.query.filter_by(name=tournament_name).first()
        if not tournament:
            click.echo(f"Tournament '{tournament_name}' not found.")
            return

        existing_participants = TournamentParticipant.query.filter_by(
            tournament_id=tournament.id
        ).all()
        current_count = len(existing_participants)
        available_slots = tournament.max_participants - current_count

        if available_slots <= 0:
            click.echo(
                f"Tournament already full ({current_count}/{tournament.max_participants} participants)."
            )
            return

        to_create = min(num_participants, available_slots)
        max_ranking = max((p.ranking for p in existing_participants), default=0)

        created_users = 0
        created_participants = 0

        for i in range(to_create):
            ranking = max_ranking + i + 1
            email = f"player_{tournament.id}_{ranking}@example.com"
            user = User.query.filter_by(email=email).first()
            if not user:
                user = User(
                    first_name="Player",
                    last_name=str(ranking),
                    email=email,
                    is_active=True,
                )
                user.set_password("Password123!")
                db.session.add(user)
                created_users += 1

            license_number = f"LIC-T{tournament.id:03d}-{ranking:03d}"

            # Avoid duplicate license numbers in the same tournament
            exists = TournamentParticipant.query.filter_by(
                tournament_id=tournament.id,
                license_number=license_number,
            ).first()
            if exists:
                continue

            participant = TournamentParticipant(
                tournament_id=tournament.id,
                user_id=user.id,
                license_number=license_number,
                ranking=ranking,
                status="pending",
            )
            db.session.add(participant)
            created_participants += 1

        db.session.commit()

        click.echo(
            f"Added {created_participants} participants (created {created_users} users) "
            f"to tournament '{tournament.name}' (now {current_count + created_participants}/{tournament.max_participants})."
        )
