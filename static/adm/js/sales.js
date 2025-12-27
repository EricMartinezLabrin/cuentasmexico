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

// --- Paginación ---
let currentPage = 1;
let pageSize = 20;
let lastSearchData = [];

function renderPagination(total, page, pageSize) {
  const totalPages = Math.ceil(total / pageSize);
  let html = '<div class="pagination-controls">';
  if (totalPages <= 1) return '';
  if (page > 1) {
    html += `<button class="btn btn-sm btn-primary" onclick="goToPage(${
      page - 1
    })">Anterior</button>`;
  }
  html += ` <span>Página ${page} de ${totalPages}</span> `;
  if (page < totalPages) {
    html += `<button class="btn btn-sm btn-primary" onclick="goToPage(${
      page + 1
    })">Siguiente</button>`;
  }
  html += '</div>';
  return html;
}

function goToPage(page) {
  currentPage = page;
  sendSearchData(lastSearchData, page, pageSize);
}

const sendSearchData = (data, page = 1, pageSizeParam = 20) => {
  lastSearchData = data;
  $.ajax({
    type: 'POST',
    url: '/adm/sales/search',
    data: {
      csrfmiddlewaretoken: csrf,
      'data[]': data,
      page: page,
      page_size: pageSizeParam,
    },
    success: (res) => {
      const data = res.data;
      const total = res.total || 0;
      const page = res.page || 1;
      const pageSize = res.page_size || 20;
      if (Array.isArray(data)) {
        resultsBox.innerHTML = '';
        data.forEach((data) => {
          resultsBox.innerHTML += `
            <td><input class="form-check-input details" name="serv" id="${
              data.id
            }" type="checkbox" value="${data.id}" onclick="detail()"></td>
            <label for="${data.id}">
            <td><img src="${data.logo}" width="20"></td>
            <td>${data.email}</td>
            <td>${data.password}</td>
            <td>${moment(data.expiration_acc).format('DD/MM/YYYY')}</td>
            <td>${data.profile}</td>            
            <br>
            </label>
          `;
        });
        // Renderizar controles de paginación
        resultsBox.innerHTML += renderPagination(total, page, pageSize);
      } else {
        resultsBox.innerHTML = `<b>${data}</b>`;
        accounts.classList.add('not-visible');
      }
    },
  });
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
            <td><img src="${data.logo}" width="20"></td>
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
  console.log(det);
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
      arr.push(e.value);
    }
  });
  accounts.classList.remove('not-visible');
  currentPage = 1;
  sendSearchData(arr, currentPage, pageSize);
}

function CheckFields() {
  console.log(duration.value);
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
      console.log(res);
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
