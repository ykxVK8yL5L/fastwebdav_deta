class AesCTR {
  constructor(password, sizeSalt) {
    this.password = password
    this.sizeSalt = sizeSalt + ''
    // check base64
    if (password.length !== 32) {
      //this.passwdOutward = crypto.pbkdf2Sync(this.password, 'AES-CTR', 1000, 16, 'sha256').toString('hex')
      // const key = CryptoJS.PBKDF2(this.password, 'AES-CTR', { keySize: 128/32, iterations: 1000, hasher: CryptoJS.algo.SHA256 });
      // // 将密钥派生转换为十六进制字符串
      // const keyHex = key.toString(CryptoJS.enc.Hex);

      const key = CryptoJS.PBKDF2(this.password, 'AES-CTR', {
          keySize: 4, 
          iterations: 1000,
          hasher: CryptoJS.algo.SHA256
      });
    
      // 将密钥转换为十六进制字符串
      const keyHex = key.toString();
      this.passwdOutward = keyHex;
    }
    // create file aes-ctr key
    const passwdSalt = this.passwdOutward + sizeSalt
    // this.key = crypto.createHash('md5').update(passwdSalt).digest()
    // this.iv = crypto.createHash('md5').update(this.sizeSalt).digest()

    this.key = CryptoJS.MD5(passwdSalt)
    this.iv = CryptoJS.MD5(this.sizeSalt)

    // copy to soureIv
    const ivBuffer = new ArrayBuffer(this.iv.length)
    this.iv = ivBuffer;
    this.soureIv = ivBuffer
    // this.cipher = crypto.createCipheriv('aes-128-ctr', this.key, this.iv)
    this.cipher = CryptoJS.algo.AES.createEncryptor(CryptoJS.enc.Utf8.parse(this.key), { iv: CryptoJS.enc.Utf8.parse(this.iv) });
  }

  encrypt(messageBytes) {
    return this.cipher.update(messageBytes)
  }

  decrypt(messageBytes) {
    return this.cipher.update(messageBytes)
  }

  // reset position
  incrementIV(increment) {
    const MAX_UINT32 = 0xffffffff
    const incrementBig = ~~(increment / MAX_UINT32)
    const incrementLittle = (increment % MAX_UINT32) - incrementBig
    // split the 128bits IV in 4 numbers, 32bits each
    let overflow = 0
    for (let idx = 0; idx < 4; ++idx) {
      let num = this.iv.readUInt32BE(12 - idx * 4)
      let inc = overflow
      if (idx === 0) inc += incrementLittle
      if (idx === 1) inc += incrementBig
      num += inc
      const numBig = ~~(num / MAX_UINT32)
      const numLittle = (num % MAX_UINT32) - numBig
      overflow = numBig
      this.iv.writeUInt32BE(numLittle, 12 - idx * 4)
    }
  }
}

