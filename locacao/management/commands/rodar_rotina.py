from datetime import date

from django.core.management.base import BaseCommand

from locacao.rotina import executar


class Command(BaseCommand):
    help = "Roda a rotina diária agora, processando os dias pendentes até hoje (ou até --ate)."

    def add_arguments(self, parser):
        parser.add_argument("--ate", type=date.fromisoformat, help="Último dia a processar (AAAA-MM-DD).")

    def handle(self, *args, ate=None, **options):
        dias = executar(ate)
        if dias:
            self.stdout.write(f"Dias processados: {dias[0]:%d/%m/%Y} a {dias[-1]:%d/%m/%Y}")
        else:
            self.stdout.write("Nenhum dia pendente.")
