#!/usr/bin/osascript

on run
    try
        -- Ask for administrator password
        set adminPassword to text returned of (display dialog "Enter administrator password to stop kanata service:" default answer "" with hidden answer buttons {"Cancel", "OK"} default button "OK")
        
        -- Stop the launchd service
        set stopCommand to "echo '" & adminPassword & "' | sudo -S launchctl stop com.keypath.kanata"
        do shell script stopCommand
        
        -- Unload the service
        set unloadCommand to "echo '" & adminPassword & "' | sudo -S launchctl unload /Library/LaunchDaemons/com.keypath.kanata.plist"
        do shell script unloadCommand
        
        -- Kill any remaining kanata processes
        set killCommand to "echo '" & adminPassword & "' | sudo -S pkill -9 kanata"
        do shell script killCommand
        
        display notification "Kanata service stopped successfully" with title "Kanata Manager"
        return "SUCCESS: Kanata service stopped"
        
    on error errMsg
        display dialog "Error stopping kanata: " & errMsg buttons {"OK"} default button "OK"
        return "ERROR: " & errMsg
    end try
end run