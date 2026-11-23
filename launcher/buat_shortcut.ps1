# Membuat shortcut "GUI BP" (ikon samping.png, tanpa konsol) di folder proyek (akar) dan Desktop.
# Jalankan ulang bila folder proyek dipindah:
#   powershell -ExecutionPolicy Bypass -File launcher\buat_shortcut.ps1
$root = Split-Path -Parent $PSScriptRoot        # akar proyek
$pyw  = (Get-Command pythonw.exe -ErrorAction Stop).Source
$ico  = Join-Path $root "app\assets\icons\GUI_BP.ico"
$sh   = New-Object -ComObject WScript.Shell
foreach ($dir in @($root, [Environment]::GetFolderPath("Desktop"))) {
    $lnk = $sh.CreateShortcut((Join-Path $dir "GUI BP.lnk"))
    $lnk.TargetPath       = $pyw
    $lnk.Arguments        = '"' + (Join-Path $root "launcher\GUI_BP.pyw") + '"'
    $lnk.WorkingDirectory = $root
    $lnk.IconLocation     = "$ico,0"
    $lnk.Description      = "GUI BP - Balancing Propeller"
    $lnk.Save()
    Write-Output "Dibuat: $dir\GUI BP.lnk"
}
