from django.core.management.base import BaseCommand

from adm.functions.sync_pyc_sheets import (
    _is_explicit_ignored_unmapped_service,
    PycSheetSyncService,
    _build_google_access_token,
    _needs_replacement_by_external_status,
    _tab_from_service,
)
from adm.models import Account


class Command(BaseCommand):
    help = "Preview (dry-run) del sync PYC: muestra acciones sin modificar DB."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Máximo de cuentas a mostrar (0 = todas).",
        )
        parser.add_argument(
            "--only-actions",
            action="store_true",
            help="Muestra solo cuentas con cambios/acciones.",
        )

    def handle(self, *args, **options):
        limit = max(0, int(options.get("limit") or 0))
        only_actions = bool(options.get("only_actions"))

        self.stdout.write(self.style.SUCCESS("Iniciando preview dry-run sync PYC..."))

        service = PycSheetSyncService()
        token = _build_google_access_token()
        tab_index, tab_loose_index = service._build_tab_index(token)

        accounts = (
            Account.objects.select_related("account_name", "customer")
            .filter(supplier__name__iexact="pyc")
            .order_by("id")
        )

        total = accounts.count()
        shown = 0
        no_changes = 0
        projected_active_without_customer_by_service = {}
        actions_summary = {
            "explicitly_ignored_unmapped": 0,
            "unmapped_ignored": 0,
            "would_mark_deleted": 0,
            "would_change_password": 0,
            "would_change_external_status": 0,
            "would_change_profile": 0,
            "would_reactivate": 0,
            "would_replace_customer_account": 0,
        }

        for account in accounts:
            if limit and shown >= limit:
                break

            if _is_explicit_ignored_unmapped_service(account.account_name.description):
                actions_summary["explicitly_ignored_unmapped"] += 1
                projected_active_without_customer_by_service.setdefault(account.account_name.description, 0)
                if account.status and account.customer_id is None:
                    projected_active_without_customer_by_service[account.account_name.description] += 1
                continue

            tab_name = _tab_from_service(account.account_name.description)
            if not tab_name:
                actions_summary["unmapped_ignored"] += 1
                projected_active_without_customer_by_service.setdefault(account.account_name.description, 0)
                if account.status and account.customer_id is None:
                    projected_active_without_customer_by_service[account.account_name.description] += 1
                if not only_actions:
                    self.stdout.write(
                        f"[IGNORAR] account_id={account.id} email={account.email} "
                        f"service={account.account_name.description} -> servicio sin mapeo"
                    )
                    shown += 1
                continue

            row, match_type = service._find_row_with_double_check(
                account=account,
                tab_name=tab_name,
                tab_index=tab_index,
                tab_loose_index=tab_loose_index,
            )

            account_actions = []
            projected_status = account.status
            if not row:
                if match_type == "not_found":
                    actions_summary["would_mark_deleted"] += 1
                    account_actions.append("no match en sheet -> deleted + status=False")
                    projected_status = False
                    if account.customer_id:
                        actions_summary["would_replace_customer_account"] += 1
                        account_actions.append("tiene customer -> intentaría reemplazo automático")
                elif match_type == "ambiguous":
                    account_actions.append("match ambiguo (email flexible) -> no marcar deleted")
                else:
                    account_actions.append("sin match -> no acción")
            else:
                if row.status and account.external_status != row.status:
                    actions_summary["would_change_external_status"] += 1
                    account_actions.append(f"external_status: {account.external_status} -> {row.status}")

                if row.password and account.password != row.password:
                    actions_summary["would_change_password"] += 1
                    account_actions.append(f"password -> {row.password}")

                if row.profile is not None and account.profile != row.profile:
                    actions_summary["would_change_profile"] += 1
                    account_actions.append(f"profile: {account.profile} -> {row.profile}")

                if not _needs_replacement_by_external_status(row.status) and not account.status:
                    actions_summary["would_reactivate"] += 1
                    account_actions.append("status False -> True (reactivar)")
                    projected_status = True

                target_status = row.status or account.external_status
                if _needs_replacement_by_external_status(target_status) and account.customer_id:
                    actions_summary["would_replace_customer_account"] += 1
                    account_actions.append("external_status deleted/suspendida con customer -> intentaría reemplazo")

            projected_active_without_customer_by_service.setdefault(account.account_name.description, 0)
            if projected_status and account.customer_id is None:
                projected_active_without_customer_by_service[account.account_name.description] += 1

            if not account_actions:
                no_changes += 1
                if not only_actions:
                    self.stdout.write(
                        f"[SIN CAMBIOS] account_id={account.id} email={account.email} "
                        f"service={account.account_name.description} tab={tab_name}"
                    )
                    shown += 1
                continue

            self.stdout.write(
                f"[ACCION] account_id={account.id} email={account.email} "
                f"service={account.account_name.description} tab={tab_name} match={match_type}"
            )
            for action in account_actions:
                self.stdout.write(f"  - {action}")
            shown += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Resumen preview dry-run"))
        self.stdout.write(f"- total_pyc_accounts: {total}")
        self.stdout.write(f"- shown: {shown}")
        self.stdout.write(f"- no_changes: {no_changes}")
        self.stdout.write(f"- explicitly_ignored_unmapped: {actions_summary['explicitly_ignored_unmapped']}")
        self.stdout.write(f"- unmapped_ignored: {actions_summary['unmapped_ignored']}")
        self.stdout.write(f"- would_mark_deleted: {actions_summary['would_mark_deleted']}")
        self.stdout.write(f"- would_change_password: {actions_summary['would_change_password']}")
        self.stdout.write(f"- would_change_external_status: {actions_summary['would_change_external_status']}")
        self.stdout.write(f"- would_change_profile: {actions_summary['would_change_profile']}")
        self.stdout.write(f"- would_reactivate: {actions_summary['would_reactivate']}")
        self.stdout.write(f"- would_replace_customer_account: {actions_summary['would_replace_customer_account']}")
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Activas proyectadas sin cliente por servicio"))
        for service_name in sorted(projected_active_without_customer_by_service.keys()):
            self.stdout.write(f"- {service_name}: {projected_active_without_customer_by_service[service_name]}")
