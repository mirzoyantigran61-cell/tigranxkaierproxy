(() => {
  const translations = {
    ru: {
      chat: "Чат",
      images: "Изображения",
      dashboard: "Панель",
      account: "Аккаунт",
      settings: "Настройки",
      server: "Управление сервером",
      logout: "Выйти"
    },

    en: {
      chat: "Chat",
      images: "Images",
      dashboard: "Dashboard",
      account: "Account",
      settings: "Settings",
      server: "Server Controls",
      logout: "Logout"
    },

    hy: {
      chat: "Չատ",
      images: "Պատկերներ",
      dashboard: "Վահանակ",
      account: "Հաշիվ",
      settings: "Կարգավորումներ",
      server: "Սերվերի կառավարում",
      logout: "Դուրս գալ"
    }
  };

  let language =
    localStorage.getItem(
      "tigran_language"
    ) || "ru";

  function t(key) {
    return (
      translations[language]?.[key]
      ||
      translations.ru[key]
      ||
      key
    );
  }

  function setLanguage(value) {
    if (
      !translations[value]
    ) {
      return;
    }

    language = value;

    localStorage.setItem(
      "tigran_language",
      value
    );
  }

  window.TigranI18N = {
    t,
    setLanguage,
    getLanguage:
      () => language
  };
})();
