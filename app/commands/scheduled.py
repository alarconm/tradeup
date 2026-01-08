"""
CLI Commands for Scheduled Tasks.

These commands can be run manually or via cron jobs:

# Monthly credit distribution (run on 1st of each month at 6 AM)
0 6 1 * * cd /app && flask scheduled monthly-credits --tenant-id=1

# Credit expiration (run daily at midnight)
0 0 * * * cd /app && flask scheduled expire-credits --tenant-id=1

# Expiration warnings (run daily at 9 AM)
0 9 * * * cd /app && flask scheduled expiration-warnings --tenant-id=1 --days=7
"""

import click
from flask import current_app
from flask.cli import with_appcontext
from ..extensions import db
from ..services.scheduled_tasks import scheduled_tasks_service
from ..models.tenant import Tenant


@click.group('scheduled')
def scheduled_cli():
    """Scheduled task commands."""
    pass


@scheduled_cli.command('monthly-credits')
@click.option('--tenant-id', type=int, help='Specific tenant ID (or all if not specified)')
@click.option('--dry-run', is_flag=True, help='Preview without issuing credits')
@with_appcontext
def distribute_monthly_credits(tenant_id, dry_run):
    """
    Distribute monthly credits to eligible members.

    Run this on the 1st of each month.
    """
    if tenant_id:
        tenants = [Tenant.query.get(tenant_id)]
        if not tenants[0]:
            click.echo(f"Tenant {tenant_id} not found")
            return
    else:
        tenants = Tenant.query.filter_by(subscription_active=True).all()

    total_credited = 0
    total_amount = 0

    for tenant in tenants:
        click.echo(f"\n{'[DRY RUN] ' if dry_run else ''}Processing tenant: {tenant.shop_domain}")

        result = scheduled_tasks_service.distribute_monthly_credits(
            tenant_id=tenant.id,
            dry_run=dry_run
        )

        click.echo(f"  Processed: {result['processed']} members")
        click.echo(f"  Credited: {result['credited']} members")
        click.echo(f"  Skipped: {result['skipped']} (already received this month)")
        click.echo(f"  Amount: ${result['total_amount']:.2f}")

        if result['errors']:
            click.echo(f"  Errors: {len(result['errors'])}")
            for error in result['errors'][:5]:
                click.echo(f"    - Member {error['member_id']}: {error['error']}")

        total_credited += result['credited']
        total_amount += result['total_amount']

    click.echo(f"\n{'[DRY RUN] ' if dry_run else ''}TOTAL: {total_credited} members, ${total_amount:.2f}")


@scheduled_cli.command('expire-credits')
@click.option('--tenant-id', type=int, help='Specific tenant ID (or all if not specified)')
@click.option('--dry-run', is_flag=True, help='Preview without expiring credits')
@with_appcontext
def expire_credits(tenant_id, dry_run):
    """
    Expire credits that have passed their expiration date.

    Run this daily.
    """
    if tenant_id:
        tenants = [Tenant.query.get(tenant_id)]
        if not tenants[0]:
            click.echo(f"Tenant {tenant_id} not found")
            return
    else:
        tenants = Tenant.query.all()

    total_expired = 0
    total_amount = 0

    for tenant in tenants:
        click.echo(f"\n{'[DRY RUN] ' if dry_run else ''}Processing tenant: {tenant.shop_domain}")

        result = scheduled_tasks_service.expire_old_credits(
            tenant_id=tenant.id,
            dry_run=dry_run
        )

        click.echo(f"  Processed: {result['processed']} credit entries")
        click.echo(f"  Expired: {result['expired_entries']} entries")
        click.echo(f"  Members affected: {result['members_affected']}")
        click.echo(f"  Total expired: ${result['total_expired']:.2f}")

        if result['errors']:
            click.echo(f"  Errors: {len(result['errors'])}")

        total_expired += result['expired_entries']
        total_amount += result['total_expired']

    click.echo(f"\n{'[DRY RUN] ' if dry_run else ''}TOTAL: {total_expired} entries, ${total_amount:.2f}")


@scheduled_cli.command('expiration-warnings')
@click.option('--tenant-id', type=int, required=True, help='Tenant ID')
@click.option('--days', type=int, default=7, help='Days ahead to check (default: 7)')
@with_appcontext
def expiration_warnings(tenant_id, days):
    """
    Preview credits expiring within N days.

    Use this to send warning emails to members.
    """
    tenant = Tenant.query.get(tenant_id)
    if not tenant:
        click.echo(f"Tenant {tenant_id} not found")
        return

    result = scheduled_tasks_service.get_expiring_credits_preview(
        tenant_id=tenant_id,
        days_ahead=days
    )

    click.echo(f"\nCredits expiring within {days} days for {tenant.shop_domain}:")
    click.echo(f"  Members affected: {result['members_with_expiring_credits']}")
    click.echo(f"  Total amount: ${result['total_amount_expiring']:.2f}")

    if result['members']:
        click.echo(f"\n  Details:")
        for member in result['members'][:10]:
            click.echo(f"    {member['member_number']} ({member['email']}): "
                      f"${member['total_expiring']:.2f}")


@scheduled_cli.command('referral-stats')
@click.option('--tenant-id', type=int, required=True, help='Tenant ID')
@with_appcontext
def referral_stats(tenant_id):
    """
    Show referral program statistics.
    """
    tenant = Tenant.query.get(tenant_id)
    if not tenant:
        click.echo(f"Tenant {tenant_id} not found")
        return

    stats = scheduled_tasks_service.calculate_referral_stats(tenant_id)

    click.echo(f"\nReferral Stats for {tenant.shop_domain}:")
    click.echo(f"  Total referrals: {stats['total_referrals']}")
    click.echo(f"  This month: {stats['monthly_referrals']}")
    click.echo(f"  Total credit issued: ${stats['total_credit_issued']:.2f}")

    if stats['top_referrers']:
        click.echo(f"\n  Top Referrers:")
        for r in stats['top_referrers'][:5]:
            click.echo(f"    {r['member_number']}: {r['referral_count']} referrals, "
                      f"${r['referral_earnings']:.2f} earned")


def init_app(app):
    """Register CLI commands with the Flask app."""
    app.cli.add_command(scheduled_cli)
