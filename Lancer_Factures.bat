@echo off
title Generateur de Factures - Parcours Homere
color 17

echo.
echo  ================================================
echo   Generateur de Factures -- Parcours Homere
echo   Leon LEROY EI
echo  ================================================
echo.
echo  Demarrage de l'application...
echo  Ne fermez pas cette fenetre pendant l'utilisation.
echo.

:: Cherche Python automatiquement
where python >nul 2>&1
if %errorlevel% == 0 (
    set PYTHON=python
    goto :run
)

where python3 >nul 2>&1
if %errorlevel% == 0 (
    set PYTHON=python3
    goto :run
)

:: Si Python pas trouvé dans PATH, essaie les emplacements courants
if exist "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python314\python.exe" (
    set PYTHON=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python314\python.exe
    goto :run
)
if exist "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python313\python.exe" (
    set PYTHON=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python313\python.exe
    goto :run
)
if exist "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python312\python.exe" (
    set PYTHON=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python312\python.exe
    goto :run
)
if exist "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python311\python.exe" (
    set PYTHON=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python311\python.exe
    goto :run
)
if exist "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python310\python.exe" (
    set PYTHON=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python310\python.exe
    goto :run
)

echo  ERREUR : Python introuvable sur cet ordinateur.
echo  Installez Python depuis https://www.python.org
echo.
pause
exit /b 1

:run
:: Vérifier que reportlab est installé, sinon l'installer
echo  Verification de reportlab...
%PYTHON% -c "import reportlab" >nul 2>&1
if %errorlevel% neq 0 (
    echo  Installation de reportlab en cours...
    %PYTHON% -m pip install reportlab --quiet
    if %errorlevel% neq 0 (
        echo  ERREUR lors de l'installation de reportlab.
        pause
        exit /b 1
    )
    echo  reportlab installe avec succes !
)

:: Lancer l'app (elle ouvre le navigateur automatiquement)
echo  Application lancee sur http://localhost:8765
echo.
echo  Pour arreter : fermez cette fenetre.
echo.

:: On se place dans le dossier du .bat pour que app.py soit trouvé
cd /d "%~dp0"
%PYTHON% appvff.py

pause
