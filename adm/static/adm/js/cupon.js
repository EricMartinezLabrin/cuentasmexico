const redeem = document.getElementById('redeem');
const csrf = document.getElementsByName('csrfmiddlewaretoken')[0].value;
const long = document.getElementById('long');
const sendSearchData = (data) => {
  try {
    $.ajax({
      type: 'POST',
      url: '/adm/sales/search',
      data: {
        csrfmiddlewaretoken: csrf,
        'data[]': data,
      },
      success: (res) => {
        const data = res.data;
        if (Array.isArray(data)) {
          resultsBox.innerHTML = '';
          data.forEach((data, index) => {
            let borderStyle = index === 0 ? 'border: 2px solid green;' : '';
            resultsBox.innerHTML += `
            <tr style="${borderStyle}">
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
        } else {
          resultsBox.innerHTML = `<b>${data}</b>`;
          // accounts.classList.add("not-visible");
        }
      },
    });
  } catch (error) {
    console.error(error);
  }
  const resultsBox = document.getElementById('resultsBox');
};

const sendSearchDetailData = (det) => {
  document.getElementById('submit').disabled = false;
  const accdetail = document.getElementById('accdetail');
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
        document.getElementById('submit').disabled = true;
      }
    },
  });
};

redeem.addEventListener(
  'load',
  (() => {
    const arr = [];
    arr.push(JSON.stringify({ service: redeem.value, duration: long.value }));
    sendSearchData(arr);
  })()
);

function detail() {
  const details = document.getElementsByClassName('details');
  const mainAccdetail = document.getElementById('main-accdetail');

  var det = [];

  Array.prototype.filter.call(details, (e) => {
    if (e.checked == true) {
      det.push(e.value);
    }
  });
  mainAccdetail.classList.remove('not-visible');
  sendSearchDetailData(det);
}

function NotNull(string) {
  if (string == null) {
    return 'Disponible';
  } else {
    return string;
  }
}
