import click
from flask import Flask

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
