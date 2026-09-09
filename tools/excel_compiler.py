from migrate_land import main as main_3
from migrate_native_format import main as main_2
from migrate_plaats_regio import main as main_1
from _common import clear_output

def main():
    out_path = "C:/Users/MathieuButenaerts/projects/leadbeheer/excels/final.xlsx"
    clear_output(out_path)
    print(1)
    main_1("C:/Users/MathieuButenaerts/projects/leadbeheer/excels/e1.xlsx", out_path)
    print(2)
    main_2("C:/Users/MathieuButenaerts/projects/leadbeheer/excels/e2.xlsx", out_path)
    print(3)
    main_3("C:/Users/MathieuButenaerts/projects/leadbeheer/excels/e3.xlsx", out_path)
    


if __name__ == "__main__":
    main()
