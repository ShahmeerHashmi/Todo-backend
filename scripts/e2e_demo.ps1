$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$email = 'test' + (Get-Date -UFormat %s) + '@example.com'
Write-Output "Using: $email"

# Register
try {
    $reg = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/auth/register' -Method Post -Body (ConvertTo-Json @{email=$email; password='Password123!'}) -ContentType 'application/json' -WebSession $session
    Write-Output "Register response:`n$($reg.Content)"
} catch { Write-Output "Register error: $($_.Exception.Message)" }

# Login
try {
    $login = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/auth/login' -Method Post -Body (ConvertTo-Json @{email=$email; password='Password123!'}) -ContentType 'application/json' -WebSession $session
    Write-Output "Login response:`n$($login.Content)"
} catch { Write-Output "Login error: $($_.Exception.Message)" }

# Create via chat
Write-Output "`n-- Sending: Add study"
try {
    $c1 = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/chat/' -Method Post -Body (ConvertTo-Json @{message='Add study'}) -ContentType 'application/json' -WebSession $session
    Write-Output "Chat create response:`n$($c1.Content)"
} catch { Write-Output "Chat create error: $($_.Exception.Message)" }

# List tasks
Write-Output "`n-- Tasks after create"
try {
    $t1 = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/tasks' -Method Get -WebSession $session
    Write-Output $t1.Content
} catch { Write-Output "Tasks fetch error: $($_.Exception.Message)" }

# Mark complete
Write-Output "`n-- Sending: mark it as complete"
try {
    $c2 = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/chat/' -Method Post -Body (ConvertTo-Json @{message='mark it as complete'}) -ContentType 'application/json' -WebSession $session
    Write-Output "Chat complete response:`n$($c2.Content)"
} catch { Write-Output "Chat complete error: $($_.Exception.Message)" }

# List tasks
Write-Output "`n-- Tasks after complete"
try {
    $t2 = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/tasks' -Method Get -WebSession $session
    Write-Output $t2.Content
} catch { Write-Output "Tasks fetch error: $($_.Exception.Message)" }

# Delete
Write-Output "`n-- Sending: now delete it"
try {
    $c3 = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/chat/' -Method Post -Body (ConvertTo-Json @{message='now delete it'}) -ContentType 'application/json' -WebSession $session
    Write-Output "Chat delete response:`n$($c3.Content)"
} catch { Write-Output "Chat delete error: $($_.Exception.Message)" }

# Final list
Write-Output "`n-- Tasks after delete"
try {
    $t3 = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/tasks' -Method Get -WebSession $session
    Write-Output $t3.Content
} catch { Write-Output "Tasks fetch error: $($_.Exception.Message)" }

# Chat history
Write-Output "`n-- Chat history (last messages)"
try {
    $h = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/chat/messages?limit=50' -Method Get -WebSession $session
    Write-Output $h.Content
} catch { Write-Output "Chat history error: $($_.Exception.Message)" }
