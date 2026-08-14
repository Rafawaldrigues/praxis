from repositories.escritorio_repository import EscritorioRepository


def main():

    repo = EscritorioRepository()

    escritorios = repo.listar()

    for escritorio in escritorios:
        print(escritorio)


if __name__ == "__main__":
    main()