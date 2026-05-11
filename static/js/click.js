const myTable = document.getElementById('main_table');

myTable.addEventListener('click', function(event){
    const clickedCell = event.target.closest('td');
    if (!clickedCell || clickedCell.cellIndex===0) return;

    const habitId = clickedCell.parentElement.dataset.habitId;

    const dayNum = clickedCell.dataset.day;

    const newStatus = clickedCell.dataset.status==="0" ? "1" : "0";
    clickedCell.dataset.status = newStatus;
    clickedCell.innerText = newStatus;
    
    const newLog = {habit_id: habitId, 
        day: dayNum, 
        value: newStatus
    };

    fetch ('/log_habit', {
        method: 'POST',
        headers: {
            'Content-type': 'application/json',
        },
        body: JSON.stringify(newLog)
    });
    
    console.log("Sent to flask: ", newLog);
});