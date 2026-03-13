# Badminton Registration Discord Bot

A Discord bot integrated with a database to manage badminton group registrations, player lists, and payment statuses.

---

## Features
* **Automated Queue**: Automatically handles primary and waiting lists based on capacity.
* **Database Integration**: All registration and payment data are persistently stored.
* **Role-Based Access**: Distinct commands for administrators and general members.
* **Real-time Updates**: Instant confirmation and list synchronization.

---

## Commands

### Admin Operations

| Feature | Command Format | Example & Description |
| :--- | :--- | :--- |
| **Open Registration** | `!開放報名 [Date] 至 [Deadline] [Time]` | `!開放報名 2026-03-01 至 2026-02-28 22:00` <br> Default time is 23:59 if not specified. |
| **Set Capacity** | `!人數 [Limit]` | `!人數 5` <br> Must open registration first. Users exceeding this limit go to the waiting list. |
| **Close Registration** | `!結束報名` | Immediately disables the registration function. |
| **Manage Payments** | `!繳費` or `!繳費 [Date]` | Toggle "Paid / Unpaid" status via a dropdown menu. |

### Member Operations

| Feature | Command Format | Example & Description |
| :--- | :--- | :--- |
| **Register** | `[Name] +1 ([Level])` | `John +1` or `John +1 (Beginner)` <br> The system will reply with a confirmation. |
| **Cancel** | `[Name] -1` | `John -1` <br> Members can only cancel their own entries. Admins can cancel anyone. |

### General Queries

| Feature | Command Format | Description |
| :--- | :--- | :--- |
| **View List** | `!名單` or `!名單 [Date]` | Displays the confirmed list and waiting list in order of registration. |


## Standard Workflow Example

1. **Initialize Activity**:  
   `!開放報名 2026-03-01 至 2026-02-28 22:00`
2. **Set Limit**:  
   `!人數 5`
3. **Member Signup**:  
   User types `John +1` in the channel.
4. **Check Status**:  
   Type `!名單` to view the current lineup.
5. **Finalize**:  
   Admin uses `!繳費` to track payments on the day of the event.

