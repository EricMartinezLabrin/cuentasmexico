const duration = document.getElementById('duration')
const end = document.getElementById('end')
const inputListAcc = document.getElementById('bank')
const dataListAcc = document.getElementById('banklist')
const modal = document.getElementById('modal')
const modalContent = document.getElementById('modal-body')
const modalTitle = document.getElementById('modal-title')
const modalButtons = document.getElementById('modal-footer')
const paymentMethod = document.getElementById('method')
const listPaymentMethod = document.getElementById('paymentlist')
const ticket = document.getElementById('comp')
const csrf = document.getElementsByName('csrfmiddlewaretoken')[0].value;



duration.addEventListener('change',()=>{
    if(duration.value != 'None'){
      end.disabled = false;
    }else{
        end.disabled = true;
    };
  });

inputListAcc.addEventListener('change',()=>{
if (inputListAcc.value.length > 0){
    var counter = 0
    var exist = false
    try {
        while (counter <= dataListAcc.options.length){
        if (inputListAcc.value == dataListAcc.options[counter].value ){ 
        exist = true
        break;
        } else {
        counter += 1;
        }  
    }
    if (exist === false){
        modalTitle.innerHTML = `Error`;
        modalContent.innerHTML = "La cuenta ingresada no existe, porfavor verificar";
        modalButtons.innerHTML = ""
        modalButtons.innerHTML = '<button class="btn btn-primary" onclick="changeAcc()">Corregir Número de cuenta</button>';
        $("#modal").modal('show');
    }
    }catch{
    modalTitle.innerHTML = `Error`;
    modalContent.innerHTML = "La cuenta ingresada no existe, porfavor verificar";
    modalButtons.innerHTML = ""
    modalButtons.innerHTML = '<button class="btn btn-primary" onclick="changeAcc()">Corregir Número de cuenta</button>';
    $("#modal").modal('show');
    }
}
});

paymentMethod.addEventListener('change',()=>{
if (paymentMethod.value.length > 0){
    var counter = 0
    var exist = false
    try {
        while (counter <= listPaymentMethod.options.length){
        if (paymentMethod.value == listPaymentMethod.options[counter].value ){ 
        exist = true
        break;
        } else {
        counter += 1;
        }  
    }
    if (exist === false){
        modalTitle.innerHTML = `Error`;
        modalContent.innerHTML = "El metodo de pago no existe";
        modalButtons.innerHTML = ""
        modalButtons.innerHTML = '<button class="btn btn-primary" onclick="changeMethod()">Corregir metodo de pago</button>';
        $("#modal").modal('show');
    }
    }catch{
    modalTitle.innerHTML = `Error`;
    modalContent.innerHTML = "El metodo de pago no existe";
    modalButtons.innerHTML = ""
    modalButtons.innerHTML = '<button class="btn btn-primary" onclick="changeMethod()">Corregir metodo de pago</button>';
    $("#modal").modal('show');
    }
}
}); 

function changeAcc(){
inputListAcc.value=""
$('#modal').modal('hide');
}

function changeMethod(){
    paymentMethod.value="";
    $('#modal').modal('hide');
  }

ticket.addEventListener('change',()=>{
    $.ajax({
        type: 'POST',
        url: '/adm/sales/check/ticket',
        data:{
        'csrfmiddlewaretoken': csrf,
        'data':ticket.value
        },
        success: (data)=>{
        const res = data.data
        console.log(res)
        if(Array.isArray(res)){
            modalTitle.innerHTML = `El comprobante ${res[0].ticket} ya fue utilizado`
            modalContent.innerHTML = ""
            res.forEach(res=>{
            modalContent.innerHTML+=`
                <p>
                <b>E-Mail: </b> ${res.email} - <b>Cliente: </b> ${res.customer} - <b>Fecha: </b> ${res.date}
                </p>
                `
                modalButtons.innerHTML = `
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Utilizar de todas formas</button>
                <button class="btn btn-primary" onclick="changeTicket()">Cambiar Comprobante</button>
                `;
            })
            $('#modal').modal('show');
            }
            
        }
    })
}); 