const url = window.location.href;
const service = document.querySelectorAll('.serv');
const details = document.getElementsByClassName('details');
const csrf = document.getElementsByName('csrfmiddlewaretoken')[0].value;
const resultsBox = document.getElementById('results-box');
const accounts = document.getElementById('accounts');
const accdetail = document.getElementById('accdetail');
const mainAccdetail = document.getElementById('main-accdetail');
const duration = document.getElementById('duration');
const end = document.getElementById('end');
const ticket = document.getElementById('comp');
const modalContent = document.getElementById('modal-body');
const modalTitle = document.getElementById('modal-title');
const closeModal = document.getElementById('close');
const modal = document.getElementById('modal');
const inputListAcc = document.getElementById('bank');
const dataListAcc = document.getElementById('banklist');
const modalButtons = document.getElementById('modal-footer');
const paymentMethod = document.getElementById('method');
const listPaymentMethod = document.getElementById('paymentlist');
const changeService = document.getElementById('service');

// Variables para búsqueda (global para acceso desde template)
window.allAccounts = [];
let allAccounts = window.allAccounts;

const filterResults = (searchTerm) => {
  console.log('filterResults called with:', searchTerm);
  console.log('allAccounts length:', allAccounts.length);

  const filteredAccounts = allAccounts.filter((account) => {
    const matches = account.email.toLowerCase().includes(searchTerm.toLowerCase());
    console.log(`Checking ${account.email}: ${matches}`);
    return matches;
  });

  console.log('Filtered results:', filteredAccounts.length);

  resultsBox.innerHTML = '';
  if (filteredAccounts.length === 0) {
    resultsBox.innerHTML =
      '<tr><td colspan="6" class="text-center"><b>No se encontraron resultados</b></td></tr>';
    return;
  }

  filteredAccounts.forEach((data, index) => {
    let borderStyle = index === 0 ? 'border: 2px solid green;' : '';
    resultsBox.innerHTML += `
      <tr style="${borderStyle}">
        <td><input class="form-check-input details" name="serv" id="${
          data.id
        }" type="checkbox" value="${data.id}" onclick="detail()"></td>
        <label for="${data.id}">
        <td><img src="/media/${data.logo}" width="20"></td>
        <td>${data.email}</td>
        <td>${data.password}</td>
        <td>${moment(data.expiration_acc).format('DD/MM/YYYY')}</td>
        <td>${data.profile}</td>            
        <br>
        </label>
      </tr>
    `;
  });
};

// Event delegation - configurar una sola vez cuando el documento esté listo
$(document).ready(function () {
  console.log('Document ready, setting up search listener');

  // Usar event delegation para que funcione incluso si el elemento se carga después
  $(document).on('input', '#search-email', function (e) {
    const searchTerm = $(this).val();
    console.log('🔍 Search term:', searchTerm);
    console.log('📊 Total accounts:', allAccounts.length);
    filterResults(searchTerm);
  });

  console.log('✅ Search listener configured');
});

const sendSearchData = (data) => {
  try {
    $.ajax({
      type: 'POST',
      url: '/adm/sales/search',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
      },
      data: {
        csrfmiddlewaretoken: csrf,
        'data[]': data,
        page: 1,
      },
      success: (res) => {
        console.log('Response:', res);
        const responseData = res.data;

        if (Array.isArray(responseData)) {
          allAccounts = responseData;
          window.allAccounts = responseData;
          console.log('Total accounts loaded:', allAccounts.length);

          resultsBox.innerHTML = '';
          responseData.forEach((data, index) => {
            let borderStyle = index === 0 ? 'border: 2px solid green;' : '';
            resultsBox.innerHTML += `
              <tr style="${borderStyle}">
                <td><input class="form-check-input details" name="serv" id="${
                  data.id
                }" type="checkbox" value="${data.id}" onclick="detail()"></td>
                <label for="${data.id}">
                <td><img src="/media/${data.logo}" width="20"></td>
                <td>${data.email}</td>
                <td>${data.password}</td>
                <td>${moment(data.expiration_acc).format('DD/MM/YYYY')}</td>
                <td>${data.profile}</td>            
                <br>
                </label>
              </tr>
            `;
          });

          // Mostrar información de resultados
          const infoDiv = document.createElement('div');
          infoDiv.className = 'text-center mt-2';
          infoDiv.innerHTML = `<small>Se encontraron ${responseData.length} cuentas disponibles</small>`;
          resultsBox.parentElement.parentElement.appendChild(infoDiv);

          console.log('✅ Accounts loaded and ready for search');
          console.log('📧 First account email:', responseData[0]?.email);
        } else {
          resultsBox.innerHTML = `<tr><td colspan="6"><b>${responseData}</b></td></tr>`;
          allAccounts = [];
          accounts.classList.add('not-visible');
        }
      },
      error: (error) => {
        console.error('Error:', error);
      },
    });
  } catch (error) {
    console.error(error);
  }
};

const sendSearchDetailData = (det) => {
  $.ajax({
    type: 'POST',
    url: '/adm/sales/search/detail',
    data: {
      csrfmiddlewaretoken: csrf,
      'det[]': det,
    },
    success: (det) => {
      const data = det.det;

      if (Array.isArray(data)) {
        accdetail.innerHTML = '';
        data.forEach((data) => {
          accdetail.innerHTML += `
            <td><img src="/media/${data.logo}" width="20"></td>
            <td>${data.email}</td>
            <td>${NotNull(data.customer)}</td>
            <td>${data.customer_end_date}</td>
            <td>${data.profile}</td>     
            `;
        });
      } else {
        accdetail.innerHTML = `<b>${data}</b>`;
        mainAccdetail.classList.add('not-visible');
      }
    },
  });
};

function convertDateFormat(string) {
  if (string === 'Disponible') {
    return 'Disponible';
  } else {
    moment(string).format('DD/MM/YYYY');
  }
}

function NotNull(string) {
  if (string == null) {
    return 'Disponible';
  } else {
    return string;
  }
}

function detail() {
  var det = [];
  Array.prototype.filter.call(details, (e) => {
    if (e.checked == true) {
      det.push(e.value);
    }
  });
  mainAccdetail.classList.remove('not-visible');
  sendSearchDetailData(det);
}

function services() {
  var arr = [];
  service.forEach((e) => {
    if (e.checked == true) {
      console.log(e.value);
      console.log(duration.value);
      arr.push(
        JSON.stringify({
          service: e.value,
          duration: duration.value,
        })
      );
    }
  });
  if (duration.value != 'None') {
    accounts.classList.remove('not-visible');
    sendSearchData(arr);
  }
}

function CheckFields() {
  services();
  if (duration.value != 'None') {
    end.disabled = false;
  } else {
    end.disabled = true;
  }
}

function changeTicket() {
  $('#modal').modal('hide');
  ticket.value = '';
}

function changeAcc() {
  inputListAcc.value = '';
  $('#modal').modal('hide');
}

function changeMethod() {
  paymentMethod.value = '';
  $('#modal').modal('hide');
}

ticket.addEventListener('change', () => {
  $.ajax({
    type: 'POST',
    url: '/adm/sales/check/ticket',
    data: {
      csrfmiddlewaretoken: csrf,
      data: ticket.value,
    },
    success: (data) => {
      const res = data.data;
      if (Array.isArray(res)) {
        modalTitle.innerHTML = `El comprobante ${res[0].ticket} ya fue utilizado`;
        modalContent.innerHTML = '';
        res.forEach((res) => {
          modalContent.innerHTML += `
              <p>
              <b>E-Mail: </b> ${res.email} - <b>Cliente: </b> ${res.customer} - <b>Fecha: </b> ${res.date}
              </p>
            `;
          modalButtons.innerHTML = `
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Utilizar de todas formas</button>
            <button class="btn btn-primary" onclick="changeTicket()">Cambiar Comprobante</button>
            `;
        });
        $('#modal').modal('show');
      }
    },
  });
});

duration.addEventListener('change', CheckFields);

inputListAcc.addEventListener('change', () => {
  if (inputListAcc.value.length > 0) {
    var counter = 0;
    var exist = false;
    try {
      while (counter <= dataListAcc.options.length) {
        if (inputListAcc.value == dataListAcc.options[counter].value) {
          exist = true;
          break;
        } else {
          counter += 1;
        }
      }
      if (exist === false) {
        modalTitle.innerHTML = `Error`;
        modalContent.innerHTML = 'La cuenta ingresada no existe, porfavor verificar';
        modalButtons.innerHTML = '';
        modalButtons.innerHTML =
          '<button class="btn btn-primary" onclick="changeAcc()">Corregir Número de cuenta</button>';
        $('#modal').modal('show');
      }
    } catch {
      modalTitle.innerHTML = `Error`;
      modalContent.innerHTML = 'La cuenta ingresada no existe, porfavor verificar';
      modalButtons.innerHTML = '';
      modalButtons.innerHTML =
        '<button class="btn btn-primary" onclick="changeAcc()">Corregir Número de cuenta</button>';
      $('#modal').modal('show');
    }
  }
});

paymentMethod.addEventListener('change', () => {
  if (paymentMethod.value.length > 0) {
    var counter = 0;
    var exist = false;
    try {
      while (counter <= listPaymentMethod.options.length) {
        if (paymentMethod.value == listPaymentMethod.options[counter].value) {
          exist = true;
          break;
        } else {
          counter += 1;
        }
      }
      if (exist === false) {
        modalTitle.innerHTML = `Error`;
        modalContent.innerHTML = 'El metodo de pago no existe';
        modalButtons.innerHTML = '';
        modalButtons.innerHTML =
          '<button class="btn btn-primary" onclick="changeMethod()">Corregir metodo de pago</button>';
        $('#modal').modal('show');
      }
    } catch {
      modalTitle.innerHTML = `Error`;
      modalContent.innerHTML = 'El metodo de pago no existe';
      modalButtons.innerHTML = '';
      modalButtons.innerHTML =
        '<button class="btn btn-primary" onclick="changeMethod()">Corregir metodo de pago</button>';
      $('#modal').modal('show');
    }
  }
});
